import arcpy
import json
import math
import copy
import os

gRoadLayer = arcpy.GetParameterAsText(0)
gPopulationLayer = arcpy.GetParameterAsText(1)
gPopulationField = arcpy.GetParameterAsText(2)
gSupermarketLayer = arcpy.GetParameterAsText(3)
gSplitLength = arcpy.GetParameterAsText(4)
gH = arcpy.GetParameterAsText(5)
gOutputLayer = arcpy.GetParameterAsText(6)

gDesc = arcpy.Describe(gRoadLayer)
gPath = gDesc.path;

# 1. 预处理
arcpy.AddMessage("1. Pretreatment...")
# 1.1 融合数据
arcpy.AddMessage("1.1 Generate dissolve layer...")
arcpy.Delete_management("dh_dissolve")
arcpy.Dissolve_management(gRoadLayer, "dh_dissolve")
arcpy.AddMessage("Finished dissolved...")

# 1.2 炸开
arcpy.AddMessage("1.2 Generate explode layer...")
arcpy.Delete_management("dh_explode")
arcpy.MultipartToSinglepart_management("dh_dissolve", "dh_explode")
exploded_count = arcpy.GetCount_management("dh_explode").getOutput(0)
arcpy.Delete_management("dh_dissolve")
arcpy.AddMessage("Finished exploded,part-count:" + exploded_count)

# 2. 剖分
arcpy.AddMessage("2. Split...")



# 2.5 逐条读取线,并剖分
arcpy.AddMessage("2.5 Read road lines and split it...")
with arcpy.da.SearchCursor("dh_explode",("OID@", "SHAPE@", "SHAPE@LENGTH")) as linerows:
    originlinedict = dict()
    segdict = dict()    #存放剖分后的线段

    def length(p1, p2):
        return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

    def insertPoint(p1, p2, olen, rlen):	# 根据比例插入点
        ratia = rlen / olen
        x = round(p1[0] + (p2[0] - p1[0]) * ratia, 2)
        y = round(p1[1] + (p2[1] - p1[1]) * ratia, 2)
        return (x, y)

    line_index = 0
    for row in linerows:
        origin = dict()
        for part in row[1]:
            points = []
            for pnt in part:
                points.append((pnt.X, pnt.Y))


        origin["length"] = row[2]
        surpluslength = row[2]

        if origin["length"] >= int(gSplitLength) * 1.5:
            rcount = math.floor(origin["length"] / int(gSplitLength)) + 1 # 此线段要剖分的段数
            rlen = origin["length"] / rcount  # 此线段要剖分的长度
            stack = []
            templength = 0
            totallength = 0

            while(len(points) <> 0 and rcount > 0):
                if len(stack) >= 1:
                    templength = length(stack[-1], points[-1])
                    #surpluslength = surpluslength - templength
                    totallength = totallength + templength
    
                    if totallength > rlen:
                        break_length = rlen - (totallength - templength)
                        line_end = points[-1]
                        line_start = stack[-1]
                        insertpoint = insertPoint(line_start, line_end, templength, break_length)   # 非要倒着弄
                        stack.append(insertpoint)
                        seg = copy.copy(origin)
                        seg["length"] = rlen
                        seg["points"] = copy.copy(stack)
                        segdict[line_index] = seg
                        del stack[:]
                        stack.append(insertpoint)
                        line_index = line_index + 1
                        totallength = 0
                        rcount = rcount - 1
                    else:
                        stack.append(points.pop())
                else:
                    stack.append(points.pop())

            if len(stack) >= 2:		# Bug,切分存在漏洞，会出现细小的线段，待解决
                if length(stack[-1], stack[-2]) > 0.01:
                    seg = copy.copy(origin)
                    seg["points"] = copy.copy(stack)
                    seg["length"] = rlen
                    segdict[line_index] = seg
                    line_index = line_index + 1
                del stack[:]
    
        else:  # 有些线本来就很短，不足以剖分
            seg = copy.copy(origin)
            seg["points"] = points
            segdict[line_index] = seg
            line_index = line_index + 1
    del linerows
arcpy.AddMessage("Finished split lines: " + str(len(segdict)))

# 2.6 生成新要素类
arcpy.AddMessage("Generate split layer...")
arcpy.Delete_management("dh_split")
arcpy.Delete_management("dh_split.shp")

dh_split = arcpy.CreateFeatureclass_management(gDesc.path.encode('gb2312'), "dh_split", "POLYLINE", "", "DISABLED", "DISABLED", "dh_explode")
fc_fields = (   
 ("population", "LONG", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # 人口
 ("generator", "SHORT", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # 发生元，超市
 ("length", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED"),     # 剖分后的长度
 ("hemidu", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED")      # 存放核密度的值
 ) 

for fc_field in fc_fields:  
    arcpy.AddField_management(dh_split, *fc_field)

arcpy.AddMessage(dh_split)

with arcpy.da.InsertCursor('dh_split', ["length", "SHAPE@"]) as inscur:
    for k, v in segdict.iteritems():
        seg_point = arcpy.Array()
        for point in v["points"]:
            seg_point.add(arcpy.Point(point[0], point[1]))
        inscur.insertRow((v["length"], arcpy.Polyline(seg_point)))
del inscur

arcpy.AddMessage("Generated split layers...")


# 3. 人口、超市映射至最近的道路seg

arcpy.AddMessage("Begin Project...")

arcpy.Near_analysis(gPopulationLayer, dh_split, "200 Meters", "NO_LOCATION", "NO_ANGLE")
arcpy.Near_analysis(gSupermarketLayer, dh_split, "500 Meters", "NO_LOCATION", "NO_ANGLE")

arcpy.AddMessage(arcpy.GetMessages())
'''
# 这里，我们使用popdict来存储人口，superdict描述超市信息，这个"dict"应该不会很大，
# 不会超过population和supermarket的总和：
# 用法： 以"NEAR_FID"作为key，其值则为数组，一个标识人口，第二个为超市；
# 注意的是，人口数是叠加的
'''
#arcpy.AddMessage(gPopulationField)
popdict = dict()
superdict = dict()
with arcpy.da.SearchCursor(gPopulationLayer, ("NEAR_FID", gPopulationField)) as rpopcur:
    for pcur in rpopcur:
        if pcur[0] <> -1:
            if popdict.has_key(pcur[0]):
                popdict[pcur[0]] = popdict[pcur[0]] + pcur[1]
            else:
                popdict[pcur[0]] = pcur[1]


with arcpy.da.SearchCursor(gSupermarketLayer, ("NEAR_FID")) as rsupcur:
    for scur in rsupcur:
        if scur[0] <> -1:
            superdict[scur[0]] = 1


with arcpy.da.UpdateCursor('dh_split', ['OID@', "population", "generator"]) as updcur:
    for ucur in updcur:
        if popdict.has_key(ucur[0]):
            ucur[1] = popdict[ucur[0]]
        if superdict.has_key(ucur[0]):
            ucur[2] = superdict[ucur[0]]
        updcur.updateRow(ucur) 

del rpopcur, rsupcur, updcur

arcpy.AddMessage("获取范围H米内的所有要素...")
# 缓冲，筛选出generator以及split——2016年10月18日22:03:49
arcpy.Delete_management("dh_generators")
arcpy.Select_analysis("dh_split", "dh_generators", "generator = 1")


arcpy.SpatialJoin_analysis("dh_split", "dh_generators", "dh_spatialjoin", "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "WITHIN_A_DISTANCE", str(int(gH) * int(gSplitLength)) + " Meters")
arcpy.DeleteIdentical_management("dh_spatialjoin", ["Shape"]) # 必须，否则隶属于两块“supermarket”的seg会出现两次，甚至三次。。。
# 2.1 提取公共点
# arcpy.AddMessage("2.1 Extract common points...")
# arcpy.Delete_management("dh_common")
# arcpy.Intersect_analysis("dh_explode", "dh_common", "", 0.1, "POINT")
# arcpy.AddMessage("Finished extract points...")

# 计算
'''
#将数据从dh_spatialjoin中全部取出。
#以x，y坐标作为key。
#然后将以坐标来查找split及后续的population
'''
pointdict = dict()
#arcpy.AddMessage("读取dh_common...")
#with arcpy.da.SearchCursor("dh_common", ()

arcpy.AddMessage("读取dh_spatialjoin...")
linedict = dict()
with arcpy.da.SearchCursor("dh_spatialjoin", ("OID@", "population", "generator", "SHAPE@", "SHAPE@LENGTH")) as rsegcur:
    for segcur in rsegcur:
        points = []
        for part in segcur[3]:
            for pat in part:
                points.append((pat.X,pat.Y))
        pointkey1 = str(round(points[0][0], 1)) + str(round(points[0][1], 1))
        pointkey2 = str(round(points[-1][0], 1)) + str(round(points[-1][1], 1))
        if pointdict.has_key(pointkey1):
            pointdict[pointkey1].append(segcur[0])
        else:
            pointdict[pointkey1] = [segcur[0]]
        if pointdict.has_key(pointkey2):
            pointdict[pointkey2].append(segcur[0])
        else:
            pointdict[pointkey2] = [segcur[0]]

        segdict = dict()
        segdict["population"] = segcur[1]
        segdict["generator"] = segcur[2]
        segdict["length"] = segcur[4]
        segdict["hemidu"] = 0
        segdict["points"] = points
        linedict[segcur[0]] = segdict
del rsegcur

# 读取发生元
arcpy.AddMessage("读取发生元...")
generatordict = dict()
with arcpy.da.SearchCursor("dh_generators", ("OID@", "SHAPE@")) as rgcur:
    for gcur in rgcur:
        points = []
        for part in gcur[1]:
            for pat in part:
                points.append((pat.X, pat.Y))
        generatordict[rgcur[0]] = [points[0], points[-1]]


# 上一条线段的id，加上相连的point，确定与point相连的其他线段
def getSegs(pid, point):
    pids = pointdict[str(math.floor(point[0])) + str(math.floor(point[1]))]
    segs = []
    for p in pids:
        if p <> pid[0]:
            segs.append(p)
    return segs


# 核密度计算
arcpy.AddMessage("核密度计算...")
maxStep = int(gH)

for k, v in generatordict.iteritems():  # 遍历每一个发生元
    stepcount = 0
    # 首先确定发生元所在的seg
    gpid1 = pointdict[str(round(v[0][0], 1)) + str(round(v[0][1], 1))]
    gpid2 = pointdict[str(round(v[-1][0], 1)) + str(round(v[-1][1], 1))]
    gpid = list(set(gpid1).intersection(set(gpid2)))  # 取交集

    lines = []
    line1 = dict()
    line1["lineid"] = gpid[0]
    line1["point"] = v[0]
    lines.append(line1)
    line2 = dict()
    line2["lineid"] = gpid[0]
    line2["point"] = v[-1]
    lines.append(line2)
    lines2 = []
    stepedlineid = []  # 必须给一个限制，否则他们会围着圈打转儿，导致这些line的核密度值过大。所以，走过的line，就不要再走了（就目前这一趟）
    for step in range(0, maxStep + 1):   # step ：距发生元的线段数
        #arcpy.AddMessage("step: " + str(step))
        #arcpy.AddMessage(lines)
        k = (1 - float(step * step) / float(maxStep * maxStep)) * 3.0 / 4.0
        fx = 1.0 / (maxStep * maxStep) * k * 100000.0

        for l in lines:
            if l["lineid"] in stepedlineid:
                continue
            pids = pointdict[str(round(l["point"][0], 1)) + str(round(l["point"][1], 1))]
            stepedlineid.append(l["lineid"])
            linedict[l["lineid"]]["hemidu"] = linedict[l["lineid"]]["hemidu"] + fx  #叠加
            for pid in pids:
                if pid in stepedlineid and len(stepedlineid) <> 1: # 如果是刚刚走过的，就忽略.元素个数为1时，表示起始处
                    continue
                ldict = dict()
                ldict["lineid"] = pid
                tpoints = linedict[pid]["points"]
                if round(tpoints[0][0], 1) == round(l["point"][0], 1) and round(tpoints[0][1], 1) == round(l["point"][1], 1):
                    ldict["point"] = tpoints[-1]
                elif round(tpoints[-1][0], 1) == round(l["point"][0], 1) and round(tpoints[-1][1], 1) == round(l["point"][1], 1):
                    ldict["point"] = tpoints[0]
                else:
                    arcpy.AddMessage("理论上不该出现！")
                    arcpy.AddMessage(tpoints)
                    continue
                lines2.append(ldict)
        lines = copy.copy(lines2)
        del lines2[:]
    del stepedlineid[:]

# 更新
# arcpy.AddMessage("更新。。。")
# with arcpy.da.UpdateCursor('dh_spatialjoin', ('OID@', "hemidu")) as upscur:
    # for ucur in upscur:
        # if linedict.has_key(ucur[0]) and linedict[ucur[0]]["hemidu"] <> 0:
            # ucur[1] = linedict[ucur[0]]["hemidu"]
        # upscur.updateRow(ucur) 
# del upscur

# 输出
arcpy.AddMessage("输出。。。")
arcpy.Delete_management(os.path.basename(gOutputLayer))
dh_output = arcpy.CreateFeatureclass_management(gDesc.path, os.path.basename(gOutputLayer), "POLYLINE", "", "DISABLED", "DISABLED", "dh_explode")
output_fields = (   
 ("population", "LONG", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # 人口
 ("hemidu", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED")      # 存放核密度的值
 )

for output_field in output_fields:  
    arcpy.AddField_management(dh_output, *output_field)

with arcpy.da.InsertCursor(dh_output, ["hemidu", "SHAPE@"]) as inscur:
    for k, v in linedict.iteritems():
        if v["hemidu"] <> 0:
            seg_point = arcpy.Array()
            for point in v["points"]:
                seg_point.add(arcpy.Point(point[0], point[1]))
            inscur.insertRow((v["hemidu"], arcpy.Polyline(seg_point)))
del inscur

arcpy.AddMessage("Finished!")



