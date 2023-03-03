from sqllineage.runner import LineageRunner

import datahub.emitter.mce_builder as builder
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.com.linkedin.pegasus2avro.dataset import (
    DatasetLineageType,
    FineGrainedLineage,
    FineGrainedLineageDownstreamType,
    FineGrainedLineageUpstreamType,
    Upstream,
    UpstreamLineage,
)
import sys

'''
    解析目标sql文件的HiveSQL生成列级血缘，提交到datahub
    sql文件路径作为命令行参数传入脚本
    提交到datahub的platform = hive
'''


# 库名设置
def datasetUrn(tableName):
    return builder.make_dataset_urn("hive", tableName)  # platform = hive


# 表、列级信息设置
def fieldUrn(tableName, fieldName):
    return builder.make_schema_field_urn(datasetUrn(tableName), fieldName)


# 目标sql文件路径
sqlFilePath = sys.argv[1]

sqlFile = open(sqlFilePath, mode='r', encoding='utf-8')

sql = sqlFile.read().__str__()

# 获取sql血缘
result = LineageRunner(sql)

# 获取sql中的下游表名
targetTableName = result.target_tables[0].__str__()

print(result)

print('===============')

# 打印列级血缘结果
result.print_column_lineage()

print('===============')

# 获取列级血缘
lineage = result.get_column_lineage

# 字段级血缘list
fineGrainedLineageList = []

# 用于冲突检查的上游list
upStreamsList = []

# 遍历列级血缘
for columnTuples in lineage():
    # 上游list
    upStreamStrList = []

    # 下游list
    downStreamStrList = []

    # 逐个字段遍历
    for column in columnTuples:

        # 元组中最后一个元素为下游表名与字段名，其他元素为上游表名与字段名

        # 遍历到最后一个元素，为下游表名与字段名
        if columnTuples.index(column) == len(columnTuples) - 1:
            downStreamFieldName = column.raw_name.__str__()
            downStreamTableName = column.__str__().replace('.' + downStreamFieldName, '').__str__()

            # print('下游表名：' + downStreamTableName)
            # print('下游字段名：' + downStreamFieldName)

            downStreamStrList.append(fieldUrn(downStreamTableName, downStreamFieldName))
        else:
            upStreamFieldName = column.raw_name.__str__()
            upStreamTableName = column.__str__().replace('.' + upStreamFieldName, '').__str__()

            # print('上游表名：' + upStreamTableName)
            # print('上游字段名：' + upStreamFieldName)

            upStreamStrList.append(fieldUrn(upStreamTableName, upStreamFieldName))

            # 用于检查上游血缘是否冲突
            upStreamsList.append(Upstream(dataset=datasetUrn(upStreamTableName), type=DatasetLineageType.TRANSFORMED))

    fineGrainedLineage = FineGrainedLineage(upstreamType=FineGrainedLineageUpstreamType.DATASET,
                                            upstreams=upStreamStrList,
                                            downstreamType=FineGrainedLineageDownstreamType.FIELD_SET,
                                            downstreams=downStreamStrList)

    fineGrainedLineageList.append(fineGrainedLineage)

fieldLineages = UpstreamLineage(
    upstreams=upStreamsList, fineGrainedLineages=fineGrainedLineageList
)

lineageMcp = MetadataChangeProposalWrapper(
    entityUrn=datasetUrn(targetTableName),  # 下游表名
    aspect=fieldLineages
)

# 调用datahub REST API
emitter = DatahubRestEmitter('')

# Emit metadata!
emitter.emit_mcp(lineageMcp)
