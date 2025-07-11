# -*- coding: utf-8 -*-
# 创建时间:2025/7/1 22:59
# 创建人:天霄
# 基于 Python 3.11
# ========================================
# 用例层级抽象类
# ========================================
from __future__ import annotations

import datetime
import importlib
import re
import threading
import time
import traceback
import warnings
from pathlib import Path
from logging import Logger
from types import ModuleType
from typing import List, Tuple, Union, Optional, Callable, Dict, Any
from xml.dom import minidom
from lxml import etree

from .BaseType import *


class CaseLayer:
    """一个用例函数层级对象，储存关于用例函数的一些数据"""
    __count = 0  # 实例化总数
    lock = threading.Lock()
    '''用例的线程锁'''
    def __init__(self, caseFunc, module=None, *, featureLayer=None, projectLayer=None, level=Enums.Level_feature,
                 flag=None, dirName=None, locked=True, skip=False, timeout=0, frequency=15):
        """用例函数层级，储存运行状态、通过情况等。可添加步骤层级，但无论有无都不会有任何影响，应在用例函数内部实现stepLayer调用。

        :param function | IBaseCase caseFunc: 实际将执行的用例函数/类等可调用对象
        :param ModuleType module: 用例函数所在.py文件对象
        :param FeatureLayer featureLayer: 父级业务功能分类层级
        :param ProjectLayer projectLayer: 根项目层级
        :param str level: 用例级别，默认分类级（project/feature）
        :param str flag: 特殊标记：setup、teardown（这两个flag必定执行）
        :param str dirName: 所在功能分类目录名，当传入featureLayer时以其为准。
        :param bool skip: 是否跳过，默认否。（仅 `projectLayer.runBy="skip"` 有效）
        :param bool locked: 是否锁定，默认是（是-本用例只能独立运行，不允许任何用例同时并行；否-反之，若运行中的用例全部不锁定才可运行）
        :param int | float timeout: 在执行用例前检查其他用例状态、直到可运行的超时时间。（-1：永远，0：检查一次，>0：超时时间，秒）
        :param int | float frequency: 检查频率，秒
        """
        self.__caseFunc = caseFunc
        try:
            _ = self.caseFullName
        except Exception:
            raise TypeError('用例函数对象只能为：函数对象/方法对象/IBaseCase！')
        self.module = module
        self.timeout = timeout
        self.level = level
        self.skip = skip
        self.flag = flag
        self.toLog = None
        self.dtLog = None
        self.frequency = frequency
        self.loop = 1
        self.error_count = 0
        if not isinstance(caseFunc, Callable):
            raise TypeError('`caseFunc`必须为可调用对象！')
        CaseLayer.__count += 1
        self.__order = 1
        self.__running = RunningStatus.UnRun
        self.__isPass = None
        self.__dirName = dirName
        self.__locked = locked
        self.__run_count = 0
        self.__launchTime = None  # 启动执行的时间点
        self.__beginTime = None  # 用例实际开始执行的时间电（和上面的差值就是浪费的等待时间）
        self.__duration = datetime.timedelta()  # 用例用时/耗时
        self.__totalTime = datetime.timedelta()  # 启动到用例实际结束的总耗时（和上面的差值就是浪费的等待时间）
        self.__totalTime_count = datetime.timedelta()  # 循环执行时，启动到用例实际结束的总耗时合计
        self.__steps: Tuple[StepLayer, ...] = ()
        self.__DataSpace = {}  # 数据空间，用于存储任意数据
        if all((featureLayer, projectLayer)) and featureLayer.projectLayer is not projectLayer:
            raise ValueError('父级FeatureLayer的根项目与传入的根项目不一致！')
        if self.level == Enums.Level_feature and featureLayer is None and not baseConfig.closeWarning:
            warnings.warn(f'feature级用例层必须有父级FeatureLayer！你应该在执行前及时赋值！用例：{self.caseNum}', RuntimeWarning, stacklevel=2)
        if self.level == Enums.Level_project and projectLayer is None and not baseConfig.closeWarning:
            warnings.warn(f'project级用例层必须有根ProjectLayer！你应该在执行前及时赋值！用例：{self.caseNum}', RuntimeWarning, stacklevel=2)
        self.__featureLayer = featureLayer
        self.__projectLayer = projectLayer
        if self.featureLayer is not None:
            self.__dirName = self.featureLayer.dirName
            if self not in self.featureLayer.caseLayerList:
                self.featureLayer.addCaseLayer(self)
        self.__CaseStatus = OneCaseStatus(
            caseNum=self.caseNum,
            caseTitle=self.caseTitle,
            level=self.level,
            featureName=self.dirName,
            running=self.running,
            isPass=self.isPass,
            duration=self.duration,
            totalTime=self.totalTime,
            runCount=self.run_count,
        )

    def __str__(self): return self.descriptionFull
    def __repr__(self): return f'CaseLayer(caseFunc={self.caseFunc.__name__}{f", module={self.module.__name__}" if self.module else ""})'

    @property
    def descriptionDetails(self):
        """最详细的自我描述"""
        if not self.steps:
            return self.descriptionFull
        xml_str = self.descriptionFull
        tree: etree._ElementTree = etree.ElementTree(etree.fromstring(xml_str))
        root: etree._Element = tree.getroot()
        stepsEle: etree._Element = root.find('steps')
        for step in self.steps:
            step_tree: etree._ElementTree = etree.ElementTree(etree.fromstring(step.descriptionFull))
            step_root: etree._Element = step_tree.getroot()
            step_root.set('stepName', str(step.stepName))
            stepsEle.append(step_root)
        new_xml = minidom.parseString(etree.tostring(tree.getroot()).replace(b'\n',b'').replace(b'\t',b'')).toprettyxml()
        new_xml: str = new_xml.replace('<?xml version="1.0" ?>', '')
        return new_xml

    @property
    def descriptionFull(self):
        """完整自我描述"""
        root = etree.Element('CaseLayer')  # 根节点
        etree.SubElement(root, 'id', attrib={'value': str(id(self))})
        etree.SubElement(root, 'caseNum', attrib={'value': str(self.caseNum)})
        etree.SubElement(root, 'level', attrib={'value': str(self.level)})
        etree.SubElement(root, 'flag', attrib={'value': str(self.flag)})
        etree.SubElement(root, 'tag', attrib={'value': ','.join(self.tag)})
        etree.SubElement(root, 'skip', attrib={'value': str(self.skip)})
        etree.SubElement(root, 'running', attrib={'value': str(self.running.name)})
        etree.SubElement(root, 'isPass', attrib={'value': str(self.isPass)})
        etree.SubElement(root, 'locked', attrib={'value': str(self.locked)})
        etree.SubElement(root, 'duration', attrib={'value': str(self.duration)})
        etree.SubElement(root, 'order', attrib={'value': str(self.order)})
        etree.SubElement(root, 'loop', attrib={'value': str(self.loop)})
        etree.SubElement(root, 'run_count', attrib={'value': str(self.run_count)})
        etree.SubElement(root, 'caseFunc', attrib={'value': str(self.caseFunc).replace('<', '‹').replace('>', '›')})
        etree.SubElement(root, 'module', attrib={'value': str(self.module).replace('<', '‹').replace('>', '›')})
        etree.SubElement(root, 'caseFullName', attrib={'value': str(self.caseFullName).replace('<', '‹').replace('>', '›')})
        _ = etree.SubElement(root, 'steps', attrib={'count': str(len(self.steps))})
        tree = etree.ElementTree(root)
        xml_str = minidom.parseString(etree.tostring(tree.getroot())).toprettyxml()
        xml_str: str = xml_str.replace('<?xml version="1.0" ?>', '')
        return xml_str

    @property
    def descriptionSimple(self):
        """简单自我描述"""
        description = f'<CaseLayer id="{id(self)}" caseNum="{self.caseNum}" level="{self.level}" flag="{self.flag}"/>'
        return description

    @property
    def id(self): return id(self)

    @property
    def caseNum(self) -> str:
        """用例编号"""
        # 用例类对象
        if isinstance(self.caseFunc, IBaseCase):
            return self.caseFunc.case_num
        # 用例类对象.run
        elif hasattr(self.caseFunc, '__self__') and isinstance(self.caseFunc.__self__, IBaseCase):
            return self.caseFunc.__self__.case_num
        # 用例函数
        return self.caseFunc.name if hasattr(self.caseFunc, 'name') else self.caseFunc.__name__  # 用例函数名

    @property
    def iBaseCase(self) -> Optional[IBaseCase]:
        """IBaseCase对象"""
        if isinstance(self.caseFunc, IBaseCase):
            return self.caseFunc
        elif hasattr(self.caseFunc, '__self__') and isinstance(self.caseFunc.__self__, IBaseCase):
            return self.caseFunc.__self__
        return None

    @property
    def caseFullName(self):
        """用例完整名称（含编号、标题，及前缀中缀后缀的格式化名称，如：`TestCase: case_001: 正常登录`）"""
        # 用例类对象
        if isinstance(self.caseFunc, IBaseCase):
            return self.caseFunc.case_full_name
        # 用例类对象.run
        elif hasattr(self.caseFunc, '__self__') and isinstance(self.caseFunc.__self__, IBaseCase):
            return self.caseFunc.__self__.case_full_name
        # 用例函数
        return ((self.caseFunc.doc if hasattr(self.caseFunc, 'doc') else self.caseFunc.__doc__) or '').strip()

    @property
    def caseTitle(self):
        """用例标题"""
        # 用例类对象
        if isinstance(self.caseFunc, IBaseCase):
            return self.caseFunc.case_title
        # 用例类对象.run
        elif hasattr(self.caseFunc, '__self__') and isinstance(self.caseFunc.__self__, IBaseCase):
            return self.caseFunc.__self__.case_title
        fullName = ((self.caseFunc.doc if hasattr(self.caseFunc, 'doc') else self.caseFunc.__doc__) or '').strip()
        return re.sub(r"^(TestCase[:：]\s*)?\s*([\w\s.:-]*)\s*[,:，：]\s*", '', fullName, flags=re.ASCII)

    @property
    def tag(self) -> Tuple[str, ...]:
        """获取用例tag"""
        # 用例类对象
        if isinstance(self.caseFunc, IBaseCase):
            return self.caseFunc.case_tag
        # 用例类对象.run
        elif hasattr(self.caseFunc, '__self__') and isinstance(self.caseFunc.__self__, IBaseCase):
            return self.caseFunc.__self__.case_tag
        # 用例函数
        elif baseConfig.tagAttributeName and hasattr(self.caseFunc, baseConfig.tagAttributeName):
            return tuple(map(lambda x: x.lower(), getattr(self.caseFunc, baseConfig.tagAttributeName)))
        # 无标签则默认为用例名+目录名（如有）
        if self.dirName:
            return self.dirName, self.caseNum
        return self.caseNum,

    @property
    def module(self):
        """用例所在模块对象"""
        if not self.__module:
            try:
                return importlib.import_module(self.caseFunc.__module__)
            except:
                pass
        return self.__module  # 用例`.py`文件对象（模块）

    @module.setter
    def module(self, module: ModuleType):
        if isinstance(module, ModuleType) or module is None:
            self.__module = module
        else:
            raise TypeError(f'请设置用例函数所在`.py`文件的`ModuleType`模块对象，而非类型`{type(module)}`！')

    @property
    def projectLayer(self):
        """根项目层级"""
        if self.__projectLayer is None:
            return self.featureLayer.projectLayer
        return self.__projectLayer

    @projectLayer.setter
    def projectLayer(self, projectLayer: ProjectLayer):
        """设置根项目层级"""
        self.__projectLayer = projectLayer

    @property
    def featureLayer(self) -> Optional['FeatureLayer']: return self.__featureLayer  # 父级FeatureLayer

    @featureLayer.setter
    def featureLayer(self, featureLayer: FeatureLayer):
        """设置父级FeatureLayer"""
        if not isinstance(featureLayer, FeatureLayer):
            self.toLog.error(f'只能设置 FeatureLayer！')
            raise TypeError('只能设置 FeatureLayer！')
        self.__featureLayer = featureLayer
        if self not in featureLayer.caseLayerList and self.flag not in ('setup', 'teardown'):
            featureLayer.addCaseLayer(self)

    @property
    def locked(self): return self.__locked  # 是否属于独立执行的用例
    @property
    def toLog(self): return self.__toLog or self.projectLayer.toLog  # 日志对象

    @toLog.setter
    def toLog(self, logger: Logger):
        """单独设置此用例的toLog日志对象"""
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__toLog = logger
        else:
            raise TypeError('logger 必须含有 info 和 error 方法！')

    @property
    def dtLog(self): return self.__dtLog or self.projectLayer.dtLog  # 日志对象

    @dtLog.setter
    def dtLog(self, logger: Logger):
        """单独设置此用例的dtLog日志对象"""
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__dtLog = logger
        else:
            raise TypeError('logger 必须含有 info 和 error 方法！')

    @property
    def arguments(self): return self.projectLayer.arguments  # 本次运行参数
    @property
    def caseFunc(self): return self.__caseFunc  # 用例类/函数对象

    @property
    def caseRunFunc(self):
        """用例执行函数"""
        # 用例类对象
        if isinstance(self.caseFunc, IBaseCase):
            return self.caseFunc.run
        # 用例类对象.run / 用例函数对象
        elif isinstance(self.caseFunc, Callable):
            return self.caseFunc
        raise TypeError('用例对象类型错误，不可执行')

    @property
    def dirName(self) -> str: return self.__dirName  # 所在目录名（功能分类名）
    @dirName.setter
    def dirName(self, dirName: str): self.__dirName = dirName
    @property
    def level(self): return self.__level  # 用例级别（project/feature）

    @level.setter
    def level(self, level: str):
        """设置用例 level （project/feature）"""
        if level not in (Enums.Level_project, Enums.Level_feature):
            raise ValueError(f'`level` only can be `project` or `feature`, but not `{level}`!')
        self.__level = level

    @property
    def order(self):
        """同一个feature下的执行次序，默认都是1"""
        return self.__order

    @order.setter
    def order(self, order: Union[int, float]):
        """设置执行次序"""
        if not isinstance(order, (int, float)):
            raise TypeError('设置次序值必须为 int/float！')
        self.__order = order

    @property
    def run_count(self) -> int:
        """已执行次数统计"""
        return self.__run_count

    @property
    def loop(self):
        """重复执行次数"""
        return self.__loop

    @loop.setter
    def loop(self, loop: int):
        """设置执行重复执行次数"""
        if not isinstance(loop, int):
            raise TypeError('设置重复执行次数值必须为 int！')
        if loop < 1:
            raise ValueError(f'设置次数最小只能为1，而非 {loop}')
        self.__loop = loop

    @property
    def flag(self): return self.__flag  # 特殊标记（setup/teardown）

    @flag.setter
    def flag(self, flag: str):
        self.__flag = flag
        if self.flag in ('setup', 'teardown'):
            self.skip = False

    @property
    def steps(self): return self.__steps  # 下级步骤层级对象
    @property
    def running(self) -> RunningStatus: return self.__running
    @property
    def isPass(self) -> Union[bool, None]: return self.__isPass  # 用例是否通过（None-尚未执行完毕，True-通过，False-不通过）
    @property
    def launchTime(self) -> Union[datetime.datetime, None]: return self.__launchTime  # 启动执行的开始时间
    @property
    def beginTime(self) -> Union[datetime.datetime, None]: return self.__beginTime  # 用例真正的开始时间（和上面的差值就是浪费的等待时间）
    @property
    def skip(self): return self.__skip

    @skip.setter
    def skip(self, skip: bool):
        """设置是否跳过"""
        if not isinstance(skip, bool):
            raise ValueError('"skip" must be bool!')
        self.__skip = skip

    @property
    def timeout(self): return self.__timeout  # 检查其他用例状态超时时间

    @timeout.setter
    def timeout(self, timeout: Union[int, float]):
        """执行用例前检查其他用例状态的超时时间。-1：永远，0：仅一次，>0：超时时间（单位：秒）"""
        if timeout < 0 and timeout != -1:
            raise ValueError(f'timeout 必须为 -1 或大于等于 0！输入值：{timeout}')
        self.__timeout = timeout

    @property
    def frequency(self): return self.__frequency  # 检查其他用例状态频率

    @frequency.setter
    def frequency(self, frequency: Union[int, float]):
        """执行用例前检查其他用例状态的频率，秒"""
        if frequency <= 0:
            raise ValueError(f'frequency 必须大于 0！输入值：{frequency}')
        self.__frequency = frequency

    @property
    def duration(self) -> datetime.timedelta:
        """纯用例的耗时。

        - 若未开始/等待/超时/跳过：耗时为 0:00:00
        - 若运行中：当前从执行用例到目前的已用时
        - 若已结束：执行用例的总耗时
        """
        if self.running == RunningStatus.Running:
            return datetime.datetime.now() - self.beginTime
        return self.__duration

    @property
    def totalTime(self) -> Optional[datetime.timedelta]:
        """执行用时，包含了等待时间。

        - 若未开始/跳过：耗时为 0:00:00
        - 若等待/运行中：当前从启动执行到目前的已用时
        - 若已结束[正常+异常]/超时：执行完毕的总耗时
        """
        if self.running in (RunningStatus.Waiting, RunningStatus.Running):
            return datetime.datetime.now() - self.launchTime
        return self.__totalTime

    @property
    def totalTime_count(self): return self.__totalTime_count  # 耗时总计

    @property
    def CaseStatus(self) -> OneCaseStatus:
        """获取当前用例状态"""
        self.__CaseStatus.isPass = self.isPass
        self.__CaseStatus.duration = self.duration
        self.__CaseStatus.totalTime = self.totalTime
        self.__CaseStatus.running = self.running
        self.__CaseStatus.runCount = self.run_count
        return self.__CaseStatus

    def setDataSpace(self, key, value):
        """设置数据"""
        self.__DataSpace[key] = value

    def getDataSpace(self, key):
        """获取数据"""
        return self.__DataSpace.get(key)

    def getRunningStep(self) -> Optional[StepLayer]:
        """获取正在执行的步骤"""
        for step in self.steps:
            if step.running == RunningStatus.Running:
                return step
        return None

    def getStepLayerByID(self, stepLayerID: int):
        """根据步骤层ID获取步骤层对象"""
        if not self.steps:
            return None
        stepLayerID = int(stepLayerID)
        for stepLayer in self.steps:
            if stepLayer.id == stepLayerID:
                return stepLayer
        return None

    def addStepLayer(self, *stepLayer: StepLayer):
        """添加步骤层对象"""
        if not all(map(lambda c: isinstance(c, StepLayer), stepLayer)):
            self.toLog.error(f'本函数只能添加 StepLayer！输入值：{stepLayer}')
            raise TypeError('本函数只能添加 StepLayer！')
        if not all(map(lambda c: c.caseLayer is self or c.caseLayer is None, stepLayer)):
            self.toLog.error(f'只能添加本用例下的 StepLayer！')
            raise TypeError('只能添加本用例下的 StepLayer！')
        for _s in stepLayer:
            if _s.caseLayer is None:
                _s.caseLayer = self
            if _s not in self.steps:
                self.__steps += (_s,)

    def getAttr(self, attrName: str):
        """从本用例载入后的对象中获取指定属性"""
        if self.module is None:
            return None
        try:
            return getattr(self.module, attrName)
        except Exception as err:
            self.toLog.error(f'无法从module获取属性：{attrName}，错误：{err}，用例层：{self}')
            raise AttributeError(err, f'无法从module获取属性：{attrName}，用例层：{self}')

    def shouldRun(self, tags='', untags=''):
        """本用例是否应执行。若给出tags，则以此tags/untags判断。

        :param tags: 选中tag，逗号分隔
        :param untags: 排除tag，逗号分隔
        :return: 是否应跑
        """
        def tagRunMode(_tags='', _untags=''):
            """通过tag方式判断是否应运行"""
            if self.flag in ('setup', 'teardown'):
                return True
            self_tag = self.tag
            if _untags:
                for _untag in _untags.split(","):
                    if _untag.lower() in self_tag:
                        return False
            # 如果 taglist 中包含任意一个 tag, 则返回True
            if _tags:
                for _tag in _tags.split(","):
                    if _tag.lower() in self_tag:
                        return True
            return False

        if tags:
            return tagRunMode(tags, untags)

        if self.projectLayer.runBy == Enums.RunBy_arguments:  # 通过tag判断是否执行
            tag = self.arguments['tag']
            untag = self.arguments.get('untag', '')
            return tagRunMode(tag, untag)
        elif self.projectLayer.runBy == Enums.RunBy_skip:  # 通过自身skip标记判断是否执行。setup/teardown不会跳过
            if self.skip and self.flag not in ('setup', 'teardown'):
                return False
            return True
        else:
            raise AttributeError(f"projectLayer.runBy 意外值：{self.projectLayer.runBy}")

    def willRun(self, *projectLayer: ProjectLayer) -> bool:
        """指定projectLayer，通过读取当前运行用例，以及是否独立运行、是否允许插队，判断本用例是否将执行

        判断逻辑：
            - 用例运行前，首先 -> 读取当前运行的用例

            - 若无其他运行用例：**【执行本用例】**  *[END]*
            - 若有其他运行用例 -> 读取自身 `locked`

                - 若自身锁定：**【继续等待】**  *[END]*
                - 若自身不锁定 -> 读取该运行中的用例的 `locked`

                    - 若任一用例锁定，或自身无步骤：**【继续等待】**  *[END]*
                    - 若所有用例不锁定：**【执行本用例】**  *[END]*

        :param projectLayer: 指定的projectLayer
        :return: 本用例是否将执行
        """
        runningFuncLayers = [caseLayer for proLayer in projectLayer for caseLayer in proLayer.getRunningCaseLayers()]
        if not runningFuncLayers:  # 1. 若无其他运行用例：本用例将运行
            return True
        # 2. 若有其他运行用例：读取自身 `locked`
        if self.locked:  # 2.1. 若自身锁定：继续等待
            return False
        # 2.2. 若自身不锁定 -> 读取该运行中的用例的 `locked`
        # 2.2.1. 若任一用例锁定，或自身无步骤：继续等待
        if not self.steps or any([caseLayer.locked for caseLayer in runningFuncLayers]):
            return False
        # 2.2.2. 若所有用例非独立执行：执行本用例
        return True

    def run(self):
        """执行这条用例（加入步骤只是方便管理，无论有无步骤都不影响。应该在用例内部实现stepLayer的调用）

        示例::

            def step1Func(*args, **kwargs): return 10
            def step2Func(*args, **kwargs): ...

            def case():  # 内部自己实现步骤之间的复杂逻辑
                num = stepLayer1.runStep(...)

                for _ in range(num):
                    stepLayer2.runStep()

                return 0

            caseLayer = CaseLayer(case, featureLayer=...)
            stepLayer1 = StepLayer(Step('步骤第一步'), step1Func, caseLayer)
            stepLayer2 = StepLayer(Step('步骤第二步', 2), step2Func, caseLayer)
            caseLayer.run()

        :return: 是否通过
        """
        self.__running = RunningStatus.UnRun
        self.__isPass = None
        # 首先，判断是否应该执行
        if not self.shouldRun():
            if self.projectLayer.runBy == Enums.RunBy_skip:
                self.__running = RunningStatus.Skipped
            return self.isPass

        # 即将执行，预先判断其他用例运行情况
        self.__running = RunningStatus.Waiting
        self.__launchTime = datetime.datetime.now()
        if self.timeout == 0:
            if not self.willRun(self.projectLayer):
                self.__running = RunningStatus.Timeout
                self.__totalTime = datetime.datetime.now() - self.launchTime
                self.__totalTime_count += self.__totalTime
                msg = f'用例执行失败，存在其他执行中的用例！本用例：{self.caseNum}'
                self.toLog.error(msg)
                return self.isPass
        else:
            willRun = False
            start = time.time()
            usetime = time.time() - start
            try:
                while usetime < self.timeout or self.timeout == -1:
                    willRun = self.willRun(self.projectLayer)
                    if willRun:
                        break
                    self.toLog.info(f'用例：{self.caseNum} 等待其他执行中的用例执行完毕... 等待间隔：{self.frequency}s')
                    time.sleep(self.frequency)
                    usetime = time.time() - start
            except CaseStopCanceled:
                self.toLog.warning(f'用例：{self.caseNum} 等待中... 已取消')
                self.dtLog.warning(f'用例：{self.caseNum} 等待中... 已取消')
                self.__running = RunningStatus.Canceled
                self.__totalTime = datetime.datetime.now() - self.launchTime
                self.__totalTime_count += self.__totalTime
                return self.isPass
            except CaseStopExit:
                self.toLog.error(f'用例：{self.caseNum} 等待中... 退出执行！')
                self.dtLog.error(f'用例：{self.caseNum} 等待中... 退出执行！')
                self.__running = RunningStatus.Killed
                self.__totalTime = datetime.datetime.now() - self.launchTime
                self.__totalTime_count += self.__totalTime
                raise
            if not willRun:
                self.__running = RunningStatus.Timeout
                self.__totalTime = datetime.datetime.now() - self.launchTime
                self.__totalTime_count += self.__totalTime
                msg = f'用例执行失败，等待其他执行中的用例执行完毕超时！用例：{self.caseNum}，等待总时长：{usetime}s'
                self.toLog.error(msg)
                return self.isPass
            if usetime >= self.frequency:
                self.toLog.info(f'用例：{self.caseNum} 等待其他执行中的用例执行完毕，等待总时长：{usetime}s')
        # 开始执行
        def main_run(oneCaseLoopMsg: OneCaseLoopMsg):
            """执行用例"""
            self.error_count = 0
            self.__running = RunningStatus.Running
            self.__beginTime = datetime.datetime.now()
            flag = self.flag or ''
            flagMsg = (f'({flag})' if flag else '').ljust(10, ' ')
            self.toLog.info(f'--> *执行用例* {flagMsg}: {self.descriptionSimple}')
            if self.projectLayer.dtLogMode in (Enums.DtLogMode_start, Enums.DtLogMode_both):
                self.dtLog.info(self.caseFullName)
            try:
                case_result = self.caseRunFunc()
                if not isinstance(case_result, type(baseConfig.successFlag)):
                    raise TypeError(f'用例函数定义应返回 {type(baseConfig.successFlag)}（{baseConfig.successFlag}表示成功），然而实际返回为{type(case_result)}')
            except CaseStopCanceled:
                self.toLog.warning(f'用例：{self.caseNum} 执行中... 已取消')
                self.dtLog.warning(f'用例：{self.caseNum} 执行中... 已取消')
                self.__running = RunningStatus.Canceled
                return self.isPass
            except CaseStopExit:
                self.toLog.error(f'用例：{self.caseNum} 执行中... 退出执行！')
                self.dtLog.error(f'用例：{self.caseNum} 执行中... 退出执行！')
                self.__running = RunningStatus.Killed
                raise
            except Exception as err:
                err_msg = f'{err.__class__.__name__}: {err}\nAt: \n{traceback.format_exc().replace(str(Path.cwd()), "")}'
                oneCaseLoopMsg.error = err_msg
                self.toLog.error(f'异常错误：{err_msg}')
                if self.projectLayer.dtLogMode in (Enums.DtLogMode_end, Enums.DtLogMode_both):
                    self.dtLog.error(f'执行用例发生异常：{err_msg}')
                self.error_count += 1
                self.__running = RunningStatus.Error
                self.__isPass = False
                return self.isPass
            else:
                self.error_count += case_result != baseConfig.successFlag
                if self.error_count == 0:
                    self.__running = RunningStatus.Finished
                    self.__isPass = True
                    return self.isPass
                self.__running = RunningStatus.Finished
                self.__isPass = False
                return self.isPass
            finally:
                self.__run_count += 1
                oneCaseLoopMsg.isPass = self.isPass
                now = datetime.datetime.now()
                oneCaseLoopMsg.duration = self.__duration = now - self.beginTime
                self.__totalTime = now - self.launchTime
                self.__totalTime_count += self.__totalTime
                oneCaseLoopMsg.stepErrors = tuple([f'Error in Step: [{stepLayer.step}]\n-----\n{stepLayer.error}'
                                                   for stepLayer in self.steps if stepLayer.error])
                self.__CaseStatus.loopMsgs += (oneCaseLoopMsg,)
                if self.projectLayer.dtLogMode in (Enums.DtLogMode_end, Enums.DtLogMode_both):
                    if self.isPass is None:
                        self.dtLog.error(f"{self.caseFullName} *** failed! *** ---execute break---")
                    elif not self.isPass:
                        self.dtLog.error(f"{self.caseFullName} *** failed! ***")
                    elif self.isPass:
                        self.dtLog.info(f"{self.caseFullName} *** succeeded! ***")

        for i in range(self.loop):
            if self.loop > 1:
                self.dtLog.info(f'循环执行用例 *Loop[{i + 1}/{self.loop}]*'.center(60, '-'))
            if not self.locked:  # 不锁定，不要求独立执行，则不需要线程锁
                main_run(OneCaseLoopMsg(loopIndex=i))
            with CaseLayer.lock:
                main_run(OneCaseLoopMsg(loopIndex=i))
        return self.isPass


from .ProjectLayer import ProjectLayer
from .FeatureLayer import FeatureLayer
from .StepLayer import StepLayer
