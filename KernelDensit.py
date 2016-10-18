import arcpy
import json
import math
import copy

gRoadLayer = arcpy.GetParameterAsText(0)
gPopulationLayer = arcpy.GetParameterAsText(1)
gPopulationField = arcpy.GetParameterAsText(2)
gSupermarketLayer = arcpy.GetParameterAsText(3)
gSplitLength = arcpy.GetParameterAsText(4)

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

# 2.1 提取公共点
arcpy.AddMessage("2.1 Extract common points...")
arcpy.Delete_management("dh_common")
arcpy.Intersect_analysis("dh_explode", "dh_common", "", "", "POINT")
arcpy.AddMessage("Finished extract points...")

# 2.2 读取公共点
arcpy.AddMessage("2.2 Read common points...")
commonpointdict = dict()
with arcpy.da.SearchCursor("dh_common", ["OID@", "FID_dh_explode", "SHAPE@X", "SHAPE@Y"]) as cursor:
    for row in cursor:
        cpoint = dict()
        cpoint["FID_dh_explode"] = row[1]
        cpoint["X"] = round(row[2], 2)
        cpoint["Y"] = round(row[3], 2)
        cpoint["commonid"] = 0
        cpoint["groupid"] = 0
        commonpointdict[row[0]] = cpoint
arcpy.AddMessage("Finished read common points...")

# 2.3 依据连通性进行分组
arcpy.AddMessage("2.3 Grouping according to common point...")
'''
Tips. Intersect工具算出来的公共点dh_common，
如果dh_common属性中两个点的FID_dh_explode有相同的值x，
那么dh_explode中OID = x 表示的折线，就是联通这两个点的线，
那么我们就给他一个相同的groupid，表示两者是“相通”的。
'''
repeatfiddict = dict()
commonid_index = 1
for k, v in commonpointdict.iteritems():
    if repeatfiddict.has_key(v["FID_dh_explode"]) <> True:
        repeatfiddict[v["FID_dh_explode"]] = k
    else:
        if commonpointdict[repeatfiddict[v["FID_dh_explode"]]]["commonid"] <> 0:
            v["commonid"] = commonpointdict[repeatfiddict[v["FID_dh_explode"]]]["commonid"]
        else:
            commonpointdict[repeatfiddict[v["FID_dh_explode"]]]["commonid"] = commonid_index
            v["commonid"] = commonid_index
            commonid_index = commonid_index + 1

tempdict = dict()
for k, v in commonpointdict.iteritems():
    if tempdict.has_key(str(v["X"])+str(v["Y"])) <> True:
        tempdict[str(v["X"])+str(v["Y"])] = []
    if v["commonid"] <> 0 and v["commonid"] not in tempdict[str(v["X"])+str(v["Y"])]:
        tempdict[str(v["X"])+str(v["Y"])].append(v["commonid"])

commondict = dict()
for k, v in tempdict.iteritems():
    if v <> False:
        for i in v:
            if commondict.has_key(i):
                tempdict[k] = list(set(v).union(set(tempdict[commondict[i]])))
                tempdict[commondict[i]] = tempdict[k]
            else:
                commondict[i] = k

max_groupid = 0
temp_groupid = 0
tempkeyvaluedict = dict()
for k, v in commonpointdict.iteritems():
    if tempkeyvaluedict.has_key(str(v["X"]) + str(v["Y"])) <> True:
        tempkeyvaluedict[str(v["X"]) + str(v["Y"])] = []
    if v["commonid"] in tempdict[str(v["X"]) + str(v["Y"])] or tempdict.has_key(str(v["X"]) + str(v["Y"])):
        if tempdict[str(v["X"]) + str(v["Y"])]:
            temp_groupid = tempdict[str(v["X"]) + str(v["Y"])][0]  # 以列表中第一个元素，作为groupid
            if temp_groupid > max_groupid:
                max_groupid = temp_groupid
            v["groupid"] = temp_groupid

arcpy.AddMessage("Finished grouping points...")


'''
#要不要对commonpointdict进行压缩，去掉冗余的数据。
#对于这个问题，明天再做思考2016年10月10日15:55:25
'''
# 2.4 压缩groupid
arcpy.AddMessage("2.5 Compass groupid...")
groupid_index = max_groupid + 1
groupidpointdict = dict()
for k, v in commonpointdict.iteritems():
    if groupidpointdict.has_key(str(v["X"]) + str(v["Y"])) == False:
        if v["groupid"]:
            groupidpointdict[str(v["X"]) + str(v["Y"])] = v["groupid"]
        else:
            groupidpointdict[str(v["X"]) + str(v["Y"])] = groupid_index
            groupid_index = groupid_index + 1
        
arcpy.AddMessage(groupidpointdict)

'''
#Tip. 存在潜在的问题：当很多条线段连接同一个点时，这个点的groupid就太大了。
#    因为设计的就是这么狗血groupid:1125781257912580125771258412586125911221312215478479
#    这里有待于优化，我先用本方法试着改过来2016年10月16日21:57:17
'''

# 2.5 逐条读取线,并剖分
arcpy.AddMessage("2.5 Read road lines and split it...")
linerows = arcpy.da.SearchCursor("dh_explode",("OID@", "SHAPE@", "SHAPE@LENGTH"))
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
            points.append((round(pnt.X, 2), round(pnt.Y, 2)))

    if groupidpointdict.has_key(str(points[0][0])+str(points[0][1])):
        origin["groupid"] = groupidpointdict[str(points[0][0])+str(points[0][1])]
    elif groupidpointdict.has_key(str(points[len(points) - 1][0]) + str(points[len(points) - 1][1])):
        origin["groupid"] = groupidpointdict[str(points[len(points) - 1][0]) + str(points[len(points) - 1][1])]
    else:
        origin["groupid"] = groupid_index
        groupid_index = groupid_index + 1
        #
        #    #Tips: 3W多条数据，大概有90条线段没有找到groupid——2016年10月17日13:54:58
        #

    origin["length"] = round(row[2], 2)
  
    if origin["length"] >= int(gSplitLength):
        rlen = origin["length"] / (math.floor(origin["length"] / int(gSplitLength)) + 1)
        stack = []
        templength = 0
        totallength = 0

        while(len(points) <> 0):
            if len(stack) >= 1:
                templength = length(stack[-1], points[-1])
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
                else:
                    stack.append(points.pop())
            else:
                stack.append(points.pop())

        if len(stack) >= 2:
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
arcpy.AddMessage("Finished split lines: " + str(len(segdict)))

# 2.6 生成新要素类
arcpy.AddMessage("Generate split layer...")
arcpy.Delete_management("dh_split")
arcpy.Delete_management("dh_split.shp")
dh_split = arcpy.CreateFeatureclass_management(gDesc.path, "dh_split", "POLYLINE", "", "DISABLED", "DISABLED", "dh_explode")
fc_fields = (   
 ("id", "LONG", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  
 ("length", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED"),  
 ("groupid", "TEXT", None, None, 256, "", "NULLABLE", "NON_REQUIRED")
 ) 

for fc_field in fc_fields:  
    arcpy.AddField_management(dh_split, *fc_field)

arcpy.AddMessage(dh_split)

with arcpy.da.InsertCursor('dh_split', ["id", "length", "groupid", "SHAPE@"]) as inscur:
    for k, v in segdict.iteritems():
        seg_point = arcpy.Array()
        for point in v["points"]:
            seg_point.add(arcpy.Point(point[0], point[1]))
        #arcpy.AddMessage(v)
        fc_groupid = str(v["groupid"])
        #
         #报错： v["groupid"]取不到值，也就是说这条线段没有获取到groupid。2016年10月16日22:50:45
        #
        if fc_groupid > 49:
            fc_groupid = fc_groupid[:49]
        inscur.insertRow((k, v["length"], fc_groupid, arcpy.Polyline(seg_point)))
del inscur

arcpy.AddMessage("Generated split layers...")


# 3. 人口、超市映射至最近的道路seg

arcpy.AddMessage("Begin Project...")

arcpy.Near_analysis(gPopulationLayer, dh_split, "200 Meters", "NO_LOCATION", "NO_ANGLE")
arcpy.Near_analysis(gSupermarketLayer, dh_split, "200 Meters", "NO_LOCATION", "NO_ANGLE")

arcpy.AddMessage(arcpy.GetMessages())





