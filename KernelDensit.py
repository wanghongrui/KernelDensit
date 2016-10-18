import arcpy
import json
import math
import copy

gRoadLayer = arcpy.GetParameterAsText(0)
gPopulationLayer = arcpy.GetParameterAsText(1)
gPopulationField = arcpy.GetParameterAsText(2)
gSupermarketLayer = arcpy.GetParameterAsText(3)
gSplitLength = arcpy.GetParameterAsText(4)
gH = arcpy.GetParameterAsText(5)

gDesc = arcpy.Describe(gRoadLayer)
gPath = gDesc.path;
'''
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

# 2.1 ��ȡ������
arcpy.AddMessage("2.1 Extract common points...")
arcpy.Delete_management("dh_common")
arcpy.Intersect_analysis("dh_explode", "dh_common", "", "", "POINT")
arcpy.AddMessage("Finished extract points...")


# 2.5 ������ȡ��,���ʷ�
arcpy.AddMessage("2.5 Read road lines and split it...")
linerows = arcpy.da.SearchCursor("dh_explode",("OID@", "SHAPE@", "SHAPE@LENGTH"))
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
            points.append((round(pnt.X, 2), round(pnt.Y, 2)))


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
    
    else:  # ��Щ�߱����ͺ̣ܶ��������ʷ�
        seg = copy.copy(origin)
        seg["points"] = points
        segdict[line_index] = seg
        line_index = line_index + 1
arcpy.AddMessage("Finished split lines: " + str(len(segdict)))

# 2.6 ������Ҫ����
arcpy.AddMessage("Generate split layer...")
arcpy.Delete_management("dh_split")
arcpy.Delete_management("dh_split.shp")
dh_split = arcpy.CreateFeatureclass_management(gDesc.path, "dh_split", "POLYLINE", "", "DISABLED", "DISABLED", "dh_explode")
fc_fields = (   
 ("population", "LONG", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # �˿�
 ("generator", "SHORT", None, None, None, "", "NON_NULLABLE", "REQUIRED"),  # ����Ԫ������
 ("length", "FLOAT", None, None, None, "", "NULLABLE", "NON_REQUIRED")      # �ʷֺ�ĳ���
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
arcpy.Near_analysis(gSupermarketLayer, dh_split, "200 Meters", "NO_LOCATION", "NO_ANGLE")

arcpy.AddMessage(arcpy.GetMessages())
'''
popdict = dict()
superdict = dict()

'''
 �������ʹ��popdict���洢�˿ڣ�superdict����������Ϣ�����"dict"Ӧ�ò���ܴ�
 ���ᳬ��population��supermarket���ܺͣ�
 �÷��� ��"NEAR_FID"��Ϊkey����ֵ��Ϊ���飬һ����ʶ�˿ڣ��ڶ���Ϊ���У�
 ע����ǣ��˿����ǵ��ӵ�
'''
arcpy.AddMessage(gPopulationField)
with arcpy.da.SearchCursor(gPopulationLayer, ("NEAR_FID", gPopulationField)) as rpopcur:
    for pcur in rpopcur:
        if pcur[0] <> -1:
            if popdict.has_key(pcur[0]):
                popdict[pcur[0]] = popdict[pcur[0]] + pcur[1]
            else:
                popdict[pcur[0]] = pcur[1]
arcpy.AddMessage(popdict)


with arcpy.da.SearchCursor(gSupermarketLayer, ("NEAR_FID")) as rsupcur:
    for scur in rsupcur:
        if pcur[0] <> -1:
            superdict[scur[0]] = 1

with arcpy.da.UpdateCursor('dh_split', ['OID@', "population", "generator"]) as updcur:
    for ucur in updcur:
        if popdict.has_key(ucur[0]):
            ucur[1] = popdict[ucur[0]]
        if superdict.has_key(ucur[0]):
            ucur[2] = superdict[ucur[0]]
        updcur.updateRow(ucur) 

del rpopcur, rsupcur, updcur

# ���壬ɸѡ��generator�Լ�split����2016��10��18��22:03:49
arcpy.Delete_management("dh_generators")
arcpy.Select_analysis("dh_split", "dh_generators", "generator = 1")

arcpy.Delete_management("dh_spatialjoin")
arcpy.SpatialJoin_analysis("dh_split", "dh_generators", "dh_spatialjoin", "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "WITHIN_A_DISTANCE", gH + " Meters")

# ����
'''
�����ݴ�dh_spatialjoin��ȫ��ȡ����
��x��y������Ϊkey��
Ȼ��������������split��������population
'''
linedict = dict()
pointdict = dict()
with arcpy.da.SearchCursor("dh_spatialjoin", ("OID@", "population", "generator", "SHAPE@", "SHAPE@LENGTH")) as rsegcur:
    for segcur in rsegcur:
        origin = dict()
        for part in segcur[3]:
            
            

