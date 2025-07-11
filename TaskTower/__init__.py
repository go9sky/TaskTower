from .BaseType import baseConfig
from .ProjectLayer import ProjectLayer, FeatureLayer, CaseLayer, RunningStatus
from .StepLayer import StepLayer
from .Step import Step, WithStep, WithLogTag
from .BaseCase import BaseCase

__version__ = '1.0'

"""
TaskTower （任务塔）
============================================================================================
任务塔：一个任务执行与状态监控装载器，也可用于自动化用例执行。旨在尽可能不侵入原代码的情况下，监控任务执行状态。
============================================================================================


最简使用示例：

---------------示例原任务代码(~/cases/case001.py)------------------
def case_001():
    print("开始测试步骤***1")
    return 0  # 默认以0代表执行成功
    
    
-------------------示例调库(~/main.py)----------------------------
from TaskTower import ProjectLayer, FeatureLayer, CaseLayer, RunningStatus
from cases.case001 import case_001

projectLayer = ProjectLayer(Path('E:/taskProject'))  # 用例项目初始化，设置项目根目录
featureLayer = FeatureLayer('cases', projectLayer)   # 模块分类初始化，设置模块分类名称、所属项目。这个名称可以是子目录名
caseLayer = CaseLayer(case_001, featureLayer=featureLayer)  # 用例初始化，设置用例函数、所属模块分类

# 重复以上两步，装载完所有分类、用例

# print(caseLayer.CaseStatus)  # 获取用例执行状态，立即返回，可随时获取

projectLayer.dtLog.info('=' * 80)
ok, no = projectLayer.run()
projectLayer.dtLog.info('=' * 80)
projectLayer.dtLog.info(f'通过用例数：{ok}，不通过用例数：{no}')
-------------------------------------------------------------------

"""