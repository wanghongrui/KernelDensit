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

# 1. Ԥ����
arcpy.AddMessage("1. Pretreatment...")
# 1.1 �ں�����
arcpy.AddMessage("1.1 Generate dissolve layer...")
arcpy.Delete_management("dh_dissolve")
arcpy.Dissolve_management(gRoadLayer, "dh_dissolve")
arcpy.AddMessage("Finished dissolved...")

# 1.2 ը��
arcpy.AddMessage("1.2 Generate explode layer...")
arcpy.Delete_management("dh_explode")
arcpy.MultipartToSinglepart_management("dh_dissolve", "dh_explode")
exploded_count = arcpy.GetCount_management("dh_explode").getOutput(0)
arcpy.Delete_management("dh_dissolve")
arcpy.AddMessage("Finished exploded,part-count:" + exploded_count)

# 2. �ʷ�
arcpy.AddMessage("2. Split...")



# 2.5 ������ȡ��,���ʷ�
arcpy.AddMessage("2.5 Read road lines and split it...")
with arcpy.da.SearchCursor("dh_explode",("OID@", "SHAPE@", "SHAPE@LENGTH")) as linerows:
    originlinedict = dict()
    segdict = dict()    #����ʷֺ���߶�

    def length(p1, p2):
        return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

    def insertPoint(p1, p2, olen, rlen):	# ���ݱ��������
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
            rcount = math.floor(origin["length"] / int(gSplitLength)) + 1 # ���߶�Ҫ�ʷֵĶ���
            rlen = origin["length"] / rcount  # ���߶�Ҫ�ʷֵĳ���
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
                        insertpoint = insertPoint(line_start, line_end, templength, break_length)   # ��Ҫ����Ū
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

            if len(stack) >= 2:		# Bug,�зִ���©���������ϸС���߶Σ������
                if length(stack[-1], stack[-2]) > 0.01:
                    seg = copy.copy(origin)
                    seg["points"] = copy.copy(stack)
                    seg["length"] = rlen
                    segdict[line_index] = seg
                    line_index = line_index + 1
                del stack[:]
    
        else:  # ��Щ�߱����ͺ̣ܶ��������ʷ�
            seg = copy.copy(origin)
            seg["points"] = points
            segdict[line_index] = seg
            line_index = line_index + 1
    del linerows
arcpy.AddMessage("Finished split lines: " + str(len(segdict)))

# 2.6 ������Ҫ����
arcpy.AddMessage("Generate split layer...")
arcpy.Delete_management("dh_split")
arcpy.Delete_management("dh_split.shp")

dh_split = arcpy.CreateFeatureclass_management(gDesc.path.encode('gb2312'), "dh_split", "POLYLINE", "", "DISABLED", "DISABLED", "dh_explode")
fc_fields = (   
 ("population", "LONG", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # �˿�
 ("generator", "SHORT", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # ����Ԫ������
 ("length", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED"),     # �ʷֺ�ĳ���
 ("hemidu", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED")      # ��ź��ܶȵ�ֵ
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


# 3. �˿ڡ�����ӳ��������ĵ�·seg

arcpy.AddMessage("Begin Project...")

arcpy.Near_analysis(gPopulationLayer, dh_split, "200 Meters", "NO_LOCATION", "NO_ANGLE")
arcpy.Near_analysis(gSupermarketLayer, dh_split, "500 Meters", "NO_LOCATION", "NO_ANGLE")

arcpy.AddMessage(arcpy.GetMessages())
'''
# �������ʹ��popdict���洢�˿ڣ�superdict����������Ϣ�����"dict"Ӧ�ò���ܴ�
# ���ᳬ��population��supermarket���ܺͣ�
# �÷��� ��"NEAR_FID"��Ϊkey����ֵ��Ϊ���飬һ����ʶ�˿ڣ��ڶ���Ϊ���У�
# ע����ǣ��˿����ǵ��ӵ�
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

arcpy.AddMessage("��ȡ��ΧH���ڵ�����Ҫ��...")
# ���壬ɸѡ��generator�Լ�split����2016��10��18��22:03:49
arcpy.Delete_management("dh_generators")
arcpy.Select_analysis("dh_split", "dh_generators", "generator = 1")


arcpy.SpatialJoin_analysis("dh_split", "dh_generators", "dh_spatialjoin", "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "WITHIN_A_DISTANCE", str(int(gH) * int(gSplitLength)) + " Meters")
arcpy.DeleteIdentical_management("dh_spatialjoin", ["Shape"]) # ���룬�������������顰supermarket����seg��������Σ��������Ρ�����
# 2.1 ��ȡ������
# arcpy.AddMessage("2.1 Extract common points...")
# arcpy.Delete_management("dh_common")
# arcpy.Intersect_analysis("dh_explode", "dh_common", "", 0.1, "POINT")
# arcpy.AddMessage("Finished extract points...")

# ����
'''
#�����ݴ�dh_spatialjoin��ȫ��ȡ����
#��x��y������Ϊkey��
#Ȼ��������������split��������population
'''
pointdict = dict()
#arcpy.AddMessage("��ȡdh_common...")
#with arcpy.da.SearchCursor("dh_common", ()

arcpy.AddMessage("��ȡdh_spatialjoin...")
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

# ��ȡ����Ԫ
arcpy.AddMessage("��ȡ����Ԫ...")
generatordict = dict()
with arcpy.da.SearchCursor("dh_generators", ("OID@", "SHAPE@")) as rgcur:
    for gcur in rgcur:
        points = []
        for part in gcur[1]:
            for pat in part:
                points.append((pat.X, pat.Y))
        generatordict[rgcur[0]] = [points[0], points[-1]]


# ��һ���߶ε�id������������point��ȷ����point�����������߶�
def getSegs(pid, point):
    pids = pointdict[str(math.floor(point[0])) + str(math.floor(point[1]))]
    segs = []
    for p in pids:
        if p <> pid[0]:
            segs.append(p)
    return segs


# ���ܶȼ���
arcpy.AddMessage("���ܶȼ���...")
maxStep = int(gH)

for k, v in generatordict.iteritems():  # ����ÿһ������Ԫ
    stepcount = 0
    # ����ȷ������Ԫ���ڵ�seg
    gpid1 = pointdict[str(round(v[0][0], 1)) + str(round(v[0][1], 1))]
    gpid2 = pointdict[str(round(v[-1][0], 1)) + str(round(v[-1][1], 1))]
    gpid = list(set(gpid1).intersection(set(gpid2)))  # ȡ����

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
    stepedlineid = []  # �����һ�����ƣ��������ǻ�Χ��Ȧ��ת����������Щline�ĺ��ܶ�ֵ�������ԣ��߹���line���Ͳ�Ҫ�����ˣ���Ŀǰ��һ�ˣ�
    for step in range(0, maxStep + 1):   # step ���෢��Ԫ���߶���
        #arcpy.AddMessage("step: " + str(step))
        #arcpy.AddMessage(lines)
        k = (1 - float(step * step) / float(maxStep * maxStep)) * 3.0 / 4.0
        fx = 1.0 / (maxStep * maxStep) * k * 100000.0

        for l in lines:
            if l["lineid"] in stepedlineid:
                continue
            pids = pointdict[str(round(l["point"][0], 1)) + str(round(l["point"][1], 1))]
            stepedlineid.append(l["lineid"])
            linedict[l["lineid"]]["hemidu"] = linedict[l["lineid"]]["hemidu"] + fx  #����
            for pid in pids:
                if pid in stepedlineid and len(stepedlineid) <> 1: # ����Ǹո��߹��ģ��ͺ���.Ԫ�ظ���Ϊ1ʱ����ʾ��ʼ��
                    continue
                ldict = dict()
                ldict["lineid"] = pid
                tpoints = linedict[pid]["points"]
                if round(tpoints[0][0], 1) == round(l["point"][0], 1) and round(tpoints[0][1], 1) == round(l["point"][1], 1):
                    ldict["point"] = tpoints[-1]
                elif round(tpoints[-1][0], 1) == round(l["point"][0], 1) and round(tpoints[-1][1], 1) == round(l["point"][1], 1):
                    ldict["point"] = tpoints[0]
                else:
                    arcpy.AddMessage("�����ϲ��ó��֣�")
                    arcpy.AddMessage(tpoints)
                    continue
                lines2.append(ldict)
        lines = copy.copy(lines2)
        del lines2[:]
    del stepedlineid[:]

# ����
# arcpy.AddMessage("���¡�����")
# with arcpy.da.UpdateCursor('dh_spatialjoin', ('OID@', "hemidu")) as upscur:
    # for ucur in upscur:
        # if linedict.has_key(ucur[0]) and linedict[ucur[0]]["hemidu"] <> 0:
            # ucur[1] = linedict[ucur[0]]["hemidu"]
        # upscur.updateRow(ucur) 
# del upscur

# ���
arcpy.AddMessage("���������")
arcpy.Delete_management(os.path.basename(gOutputLayer))
dh_output = arcpy.CreateFeatureclass_management(gDesc.path, os.path.basename(gOutputLayer), "POLYLINE", "", "DISABLED", "DISABLED", "dh_explode")
output_fields = (   
 ("population", "LONG", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # �˿�
 ("hemidu", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED")      # ��ź��ܶȵ�ֵ
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



