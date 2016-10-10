import arcpy
import json

gRoadLayer = arcpy.GetParameterAsText(0)
gSplitLength = arcpy.GetParameterAsText(1)

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

# 2.3 ������ȡ��
arcpy.AddMessage("2.3 Read road lines...")
linerows = arcpy.da.SearchCursor("dh_explode",("OID@", "SHAPE@", "SHAPE@LENGTH"))
originlinedict = dict()
for row in linerows:
    origin = dict()
    for part in row[1]:
        points = []
        for pnt in part:
            points.append([round(pnt.X, 2), round(pnt.Y, 2)])
    origin["length"] = round(row[2], 2)
    origin["points"] = points
    origin["commonid"] = 0
    originlinedict[row[0]] = origin
arcpy.AddMessage("Finished read road lines...")

# 2.4 ������ͨ�Խ��з���
arcpy.AddMessage("2.4 Grouping according to common point...")
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

groupid_index = 1000000
for k, v in commonpointdict.iteritems():
    if v["commonid"] in tempdict[str(v["X"]) + str(v["Y"])] or tempdict.has_key(str(v["X"]) + str(v["Y"])):
        _groupid = ''.join(map(str, tempdict[str(v["X"]) + str(v["Y"])]))
        if _groupid <> "":
            v["groupid"] = int(_groupid)
        else:
            v["groupid"] = groupid_index
            groupid_index = groupid_index + 1

arcpy.AddMessage("Finished grouping points...")

'''
Ҫ��Ҫ��commonpointdict����ѹ����ȥ����������ݡ�
����������⣬��������˼��2016��10��10��15:55:25
'''



