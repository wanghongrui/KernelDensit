import arcpy
import json

gRoadLayer = arcpy.GetParameterAsText(0)
gSplitLength = arcpy.GetParameterAsText(1)

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
with arcpy.da.SearchCursor("dh_common", ["OID@", "ORIG_FID", "FID_dh_explode", "SHAPE@X", "SHAPE@Y"]) as cursor:
    for row in cursor:
        cpoint = dict()
        cpoint["ORIG_FID"] = row[1]
        cpoint["FID_dh_explode"] = row[2]
        cpoint["X"] = round(row[3], 2)
        cpoint["Y"] = round(row[4], 2)
        commonpointdict[row[0]] = cpoint
arcpy.AddMessage("Finished read common points...")

# 2.3 逐条读取线
arcpy.AddMessage("2.3 Read road lines...")
linerows = arcpy.da.SearchCursor("dh_explode",("OID@", "SHAPE@", "SHAPE@LENGTH", "ORIG_FID"))
originlinedict = dict()
for row in linerows:
    origin = dict()
    for part in row[1]:
        points = []
        for pnt in part:
            points.append([round(pnt.X, 2), round(pnt.Y, 2)])
    origin["length"] = round(row[2], 2)
    origin["points"] = points
    origin["ORIG_FID"] = row[3]
    origin["group"] = 0
    originlinedict[row[0]] = origin
arcpy.AddMessage("Finished read road lines...")

# 2.4 依据连通性进行分组
arcpy.AddMessage("2.4 Grouping according to common point...")


