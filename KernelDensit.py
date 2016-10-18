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

# 2.2 ��ȡ������
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

# 2.3 ������ͨ�Խ��з���
arcpy.AddMessage("2.3 Grouping according to common point...")
'''
Tips. Intersect����������Ĺ�����dh_common��
���dh_common�������������FID_dh_explode����ͬ��ֵx��
��ôdh_explode��OID = x ��ʾ�����ߣ�������ͨ����������ߣ�
��ô���Ǿ͸���һ����ͬ��groupid����ʾ�����ǡ���ͨ���ġ�
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
            temp_groupid = tempdict[str(v["X"]) + str(v["Y"])][0]  # ���б��е�һ��Ԫ�أ���Ϊgroupid
            if temp_groupid > max_groupid:
                max_groupid = temp_groupid
            v["groupid"] = temp_groupid

arcpy.AddMessage("Finished grouping points...")


'''
#Ҫ��Ҫ��commonpointdict����ѹ����ȥ����������ݡ�
#����������⣬��������˼��2016��10��10��15:55:25
'''
# 2.4 ѹ��groupid
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
#Tip. ����Ǳ�ڵ����⣺���ܶ����߶�����ͬһ����ʱ��������groupid��̫���ˡ�
#    ��Ϊ��Ƶľ�����ô��Ѫgroupid:1125781257912580125771258412586125911221312215478479
#    �����д����Ż��������ñ��������ŸĹ���2016��10��16��21:57:17
'''

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

    if groupidpointdict.has_key(str(points[0][0])+str(points[0][1])):
        origin["groupid"] = groupidpointdict[str(points[0][0])+str(points[0][1])]
    elif groupidpointdict.has_key(str(points[len(points) - 1][0]) + str(points[len(points) - 1][1])):
        origin["groupid"] = groupidpointdict[str(points[len(points) - 1][0]) + str(points[len(points) - 1][1])]
    else:
        origin["groupid"] = groupid_index
        groupid_index = groupid_index + 1
        #
        #    #Tips: 3W�������ݣ������90���߶�û���ҵ�groupid����2016��10��17��13:54:58
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
         #���� v["groupid"]ȡ����ֵ��Ҳ����˵�����߶�û�л�ȡ��groupid��2016��10��16��22:50:45
        #
        if fc_groupid > 49:
            fc_groupid = fc_groupid[:49]
        inscur.insertRow((k, v["length"], fc_groupid, arcpy.Polyline(seg_point)))
del inscur

arcpy.AddMessage("Generated split layers...")


# 3. �˿ڡ�����ӳ��������ĵ�·seg

arcpy.AddMessage("Begin Project...")

arcpy.Near_analysis(gPopulationLayer, dh_split, "200 Meters", "NO_LOCATION", "NO_ANGLE")
arcpy.Near_analysis(gSupermarketLayer, dh_split, "200 Meters", "NO_LOCATION", "NO_ANGLE")

arcpy.AddMessage(arcpy.GetMessages())





