# -*- coding: utf-8 -*-
# 创建日期：2024/2/7
# 作者：天霄
# 简介：以业务为中心，将项目、业务功能分类、用例、用例步骤抽象定义为一个盒子进行管理
import datetime
import importlib
import pathlib
import re
import threading
import time
import traceback
import warnings
from logging import Logger
from types import ModuleType
from typing import List, Tuple, Union, Optional, Callable, Dict, Any
from xml.dom import minidom
from lxml import etree

from .Step import Step
from .BaseType import *

__all__ = ['ProjectBox', 'FeatureBox', 'CaseBox', 'StepBox', 'RunningStatus']

emptyLogger = simpleLog('BoxLogger')


class StepBox:
    """一个管理用例函数中一个步骤的盒对象，储存关于该步骤的一些数据"""
    lock = threading.Lock()
    '''步骤的线程锁'''
    def __init__(self, step, stepFunc, caseBox=None, *, locked=True, skip=False, timeout=0, frequency=15,
                 autoType='auto', failContinue=False):
        """加载步骤函数到盒对象

        :param step: 步骤名
        :param stepFunc: 步骤函数/类等可调用对象
        :param caseBox: 父级用例函数盒子
        :param locked: 是否锁定，默认是（是-必须没有其他运行中的锁定步骤时才能执行；否-视为闲置步骤，无视任何条件直接执行）
        :param skip: 是否跳过执行，默认否。
        :param timeout: 在运行步骤前检查其他步骤状态、直到可运行的超时时间。（-1：永远，0：检查一次，>0：超时时间，秒）
        :param frequency: 检查频率，秒
        :param autoType: 自动化类型（no-auto:非自动，half-auto:半自动，auto:全自动）
        :param failContinue: 失败是否继续执行，默认否。当设置True时，失败将返回StepFailContinue这个错误
        :type step: Step | str
        :type stepFunc: Callable
        :type caseBox: CaseBox
        """
        self.__running = RunningStatus.UnRun
        self.__isPass = None
        self.__step = step if isinstance(step, Step) else Step(step, parseFromMsg=True)
        self.__locked = locked
        self.__autoType = autoType
        self.__caseBox = None
        self.__failContinue = failContinue
        self.error = None
        self.caseBox = caseBox
        self.stepFunc = stepFunc
        self.skip = skip
        self.timeout = timeout
        self.frequency = frequency
        if caseBox and self not in self.caseBox.steps:
            self.caseBox.addStepBox(self)

    def __str__(self): return self.descriptionFull
    def __repr__(self): return f'StepBox(step={str(self.step)!r}, stepFunc={self.stepFunc!r})'

    @property
    def descriptionFull(self):
        """完整自我描述"""
        root = etree.Element('StepBox')  # 根节点
        etree.SubElement(root, 'id', attrib={'value': str(id(self))})
        etree.SubElement(root, 'caseNum', attrib={'value': str(self.caseNum)})
        etree.SubElement(root, 'stepName', attrib={'value': str(self.stepName)})
        etree.SubElement(root, 'running', attrib={'value': str(self.running.name)})
        etree.SubElement(root, 'isPass', attrib={'value': str(self.isPass)})
        etree.SubElement(root, 'locked', attrib={'value': str(self.locked)})
        etree.SubElement(root, 'stepFunc', attrib={'value': str(self.stepFunc).replace('<', '‹').replace('>', '›')})
        etree.SubElement(root, 'description', attrib={'value': str(self.step.description).replace('<', '‹').replace('>', '›')})
        tree = etree.ElementTree(root)
        xml_str = minidom.parseString(etree.tostring(tree.getroot())).toprettyxml()
        xml_str: str = xml_str.replace('<?xml version="1.0" ?>', '')
        return xml_str

    @property
    def descriptionSimple(self):
        """简单自我描述"""
        return f'<StepBox id="{id(self)}" caseNum="{self.caseNum}" stepName="{self.stepName}" locked="{self.locked}"/>'

    @property
    def id(self): return id(self)
    @property
    def step(self) -> Step: return self.__step  # 步骤对象
    @property
    def stepName(self): return self.step.stepName  # 步骤名，如：step1、step3-2
    @property
    def caseNum(self): return self.caseBox.caseNum
    @property
    def locked(self): return self.__locked  # 是否锁定
    @property
    def autoType(self): return self.__autoType  # 自动化类型
    @property
    def running(self) -> RunningStatus: return self.__running  # 当前执行状态（0-未运行，1-运行中，2-已结束运行且正常，3-已结束运行但存在异常）
    @property
    def isPass(self) -> Union[bool, None]: return self.__isPass  # 步骤是否通过（None-尚未执行完毕，True-通过，False-不通过）
    @property
    def toLog(self): return self.caseBox.toLog  # 日志对象

    @property
    def stepFunc(self):
        """步骤函数对象

        :rtype: Callable
        """
        return self.__stepFunc

    @stepFunc.setter
    def stepFunc(self, stepFunc: Callable):
        """设置步骤函数对象"""
        if not isinstance(stepFunc, Callable):
            raise TypeError('`stepFunc`必须为可调用对象！')
        self.__stepFunc = stepFunc

    @property
    def skip(self): return self.__skip

    @skip.setter
    def skip(self, skip: bool):
        """设置是否跳过"""
        if not isinstance(skip, bool):
            raise ValueError('"skip" must be bool!')
        self.__skip = skip

    @property
    def timeout(self): return self.__timeout  # 检查其他步骤状态超时时间

    @timeout.setter
    def timeout(self, timeout: Union[int, float]):
        """执行步骤前检查其他步骤状态的超时时间。-1：永远，0：仅一次，>0：超时时间（单位：秒）"""
        if timeout < 0 and timeout != -1:
            raise ValueError(f'timeout 必须为 -1 或大于等于 0！输入值：{timeout}')
        self.__timeout = timeout

    @property
    def frequency(self): return self.__frequency  # 检查其他步骤状态频率

    @frequency.setter
    def frequency(self, frequency: Union[int, float]):
        """执行步骤前检查其他步骤状态的频率，秒"""
        if frequency <= 0:
            raise ValueError(f'frequency 必须大于 0！输入值：{frequency}')
        self.__frequency = frequency

    @property
    def caseBox(self) -> 'CaseBox': return self.__caseBox  # 父级用例函数盒子

    @caseBox.setter
    def caseBox(self, caseBox: 'CaseBox'):
        """设置父级用例函数盒子"""
        if self.__caseBox is not None:
            raise ValueError('caseBox 已存在值！不可覆盖！')
        if not isinstance(caseBox, CaseBox):
            raise TypeError(f'caseBox 必须为 CaseBox！输入值：{caseBox}')
        self.__caseBox = caseBox
        if self not in caseBox.steps:
            caseBox.addStepBox(self)

    def withStep(self, logger=None):
        """子步骤执行上下文管理器

        :param logger: 日志对象
        :return: WithStep 上下文管理器
        """
        return self.step.withStep(logger)

    def willRun(self, runningCases=None) -> bool:
        """在运行前调用，通过读取当前运行用例的运行中的步骤，判断是否需要运行

        判断逻辑：
            - 步骤运行前，首先 -> 判断本步骤是否锁定

            - 若本步骤不锁定：**【执行本步骤】** *[END]*
            - 若本步骤锁定：-> 读取当前运行的步骤

                - 若无其他运行步骤：**【执行本步骤】** *[END]*
                - 若有其他运行步骤 -> 遍历其他步骤是否锁定

                    - 若其他步骤任一锁定：**【继续等待】** *[END]*
                    - 若其他步骤全部不锁定：**【执行本步骤】** *[END]*

        :param runningCases: 运行中的用例函数盒子集，默认读自所属用例的项目盒子
        :type runningCases: list[CaseBox]
        :return: 是否将执行
        """
        if not self.locked:  # 1. 若本步骤不锁定：执行本步骤
            return True
        # 2. 若本步骤锁定：-> 读取当前运行的步骤
        runningCases = runningCases or self.caseBox.projectBox.getRunningCaseBoxes()
        runningStepBoxs = [case.getRunningStep() for case in runningCases if case.getRunningStep() is not None]
        if not runningStepBoxs:  # 2.1 若无其他运行步骤：执行本步骤
            return True
        # 2.2 若有其他运行步骤 -> 遍历其他步骤是否锁定。 只有其他步骤全部不锁定才判断将执行。
        for step in runningStepBoxs:
            if step.locked:  # 2.2.1 若其他步骤锁定：继续等待
                return False
        return True  # 2.2.2 若其他步骤不锁定：执行本步骤

    def runStep(self, *args, **kwargs) -> Union[Any, StepFailContinue]:
        """执行该步骤，返回原结果"""
        # 将要执行，预先判断其他步骤运行情况
        # timeout: -1 永远，0 仅一次，>0 超时时间，秒
        self.__running = RunningStatus.UnRun
        self.__isPass = None
        # 首先，判断是否应该执行
        if self.skip:
            self.__running = RunningStatus.Skipped
            raise SkippedError(f'已跳过步骤：{self.step}')

        # 即将执行，预先判断其他步骤运行状态
        self.__running = RunningStatus.Waiting
        if self.timeout == 0:
            if not self.willRun():
                self.__running = RunningStatus.Timeout
                msg = f'步骤执行失败，存在其他执行中的步骤！本用例：{self.caseNum}，步骤：{self.stepName}'
                self.toLog.error(msg)
                raise ExecuteClashError(msg)
        else:
            willRun = False
            start = time.time()
            usetime = time.time() - start
            while usetime < self.timeout or self.timeout == -1:
                willRun = self.willRun()
                if willRun:
                    break
                self.toLog.info(f'步骤：{self.caseNum}-{self.stepName} 等待其他执行中的步骤执行完毕... 等待间隔：{self.frequency}s')
                time.sleep(self.frequency)
                usetime = time.time() - start
            if not willRun:
                self.__running = RunningStatus.Timeout
                msg = f'步骤执行失败，等待其他执行中的步骤执行完毕超时！步骤：{self.caseNum}-{self.stepName}，等待总时长：{usetime}s'
                self.toLog.error(msg)
                raise ExecuteTimeoutError(msg)
            if usetime >= self.frequency:
                self.toLog.info(f'步骤：{self.caseNum}-{self.stepName} 等待其他执行中的步骤执行完毕，等待总时长：{usetime}s')

        # 开始执行
        def main_runStep():
            """执行步骤"""
            self.__running = RunningStatus.Running
            self.toLog.info(f'\t\t-> *执行步骤*：{self.stepName}（用例：{self.caseNum}）')
            try:
                result = self.stepFunc(*args, **kwargs)
            except Exception as err:
                err_msg = f'{err.__class__.__name__}: {err}\nAt: \n{traceback.format_exc().replace(str(pathlib.Path.cwd()), "")}'
                self.error = err_msg
                self.toLog.error(f'异常错误：{err_msg}')
                self.__running = RunningStatus.Error
                self.__isPass = False
                if not self.__failContinue:
                    raise
                self.caseBox.error_count += 1
                return StepFailContinue(err)
            else:
                self.__running = RunningStatus.Finished
                self.__isPass = True
                return result

        if not self.locked:  # 闲置步骤则不需要线程锁
            return main_runStep()
        with StepBox.lock:
            return main_runStep()


class CaseBox:
    """一个用例函数盒对象，储存关于用例函数的一些数据"""
    __count = 0  # 实例化总数
    lock = threading.Lock()
    '''用例的线程锁'''
    def __init__(self, caseFunc, module=None, *, featureBox=None, projectBox=None, level='feature', flag=None,
                 dirName=None, locked=True, skip=True, timeout=0, frequency=15):
        """用例函数盒子，储存运行状态、通过情况等。可添加步骤盒子，但无论有无都不会有任何影响，应在用例函数内部实现stepBox调用。

        :param caseFunc: 实际将执行的用例函数/类等可调用对象
        :param module: 用例函数所在.py文件对象
        :param featureBox: 父级业务功能分类盒子
        :param projectBox: 根项目盒子
        :param level: 用例级别，默认分类级（project/feature）
        :param flag: 特殊标记：setup、teardown（这两个flag必定执行）
        :param dirName: 所在功能分类目录名，当传入featureBox时以其为准。
        :param skip: 是否跳过，默认是。（仅 `projectBox.runBy="skip"` 有效）
        :param locked: 是否锁定，默认是（是-本用例只能独立运行，不允许任何用例同时并行；否-反之，若运行中的用例全部不锁定才可运行）
        :param timeout: 在执行用例前检查其他用例状态、直到可运行的超时时间。（-1：永远，0：检查一次，>0：超时时间，秒）
        :param frequency: 检查频率，秒

        :type caseFunc: function | IBaseCase
        :type module: ModuleType
        :type featureBox: FeatureBox
        :type projectBox: ProjectBox
        :type level: str
        :type flag: str
        :type dirName: str
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
        self.kfLog = None
        self.frequency = frequency
        self.loop = 1
        self.error_count = 0
        if not isinstance(caseFunc, Callable):
            raise TypeError('`caseFunc`必须为可调用对象！')
        CaseBox.__count += 1
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
        self.__steps: Tuple[StepBox] = ()
        self.__DataSpace = {}  # 数据空间，用于存储任意数据
        if all((featureBox, projectBox)) and featureBox.projectBox is not projectBox:
            raise ValueError('父级FeatureBox的根项目与传入的根项目不一致！')
        if self.level == 'feature' and featureBox is None and not baseConfig.closeWarning:
            warnings.warn(f'feature级函数盒子必须有父级FeatureBox！你应该在执行前及时赋值！用例：{self.caseNum}', RuntimeWarning, stacklevel=2)
        if self.level == 'project' and projectBox is None and not baseConfig.closeWarning:
            warnings.warn(f'project级函数盒子必须有根ProjectBox！你应该在执行前及时赋值！用例：{self.caseNum}', RuntimeWarning, stacklevel=2)
        self.__featureBox = featureBox
        self.__projectBox = projectBox
        if self.featureBox is not None:
            self.__dirName = self.featureBox.dirName
            if self not in self.featureBox.caseBoxList:
                self.featureBox.addCaseBox(self)
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
    def __repr__(self): return f'CaseBox(caseFunc={self.caseFunc.__name__}{f", module={self.module.__name__}" if self.module else ""})'

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
        root = etree.Element('CaseBox')  # 根节点
        etree.SubElement(root, 'id', attrib={'value': str(id(self))})
        etree.SubElement(root, 'caseNum', attrib={'value': str(self.caseNum)})
        etree.SubElement(root, 'level', attrib={'value': str(self.level)})
        etree.SubElement(root, 'flag', attrib={'value': str(self.flag)})
        etree.SubElement(root, 'label', attrib={'value': ','.join(self.label)})
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
        stepsEle = etree.SubElement(root, 'steps', attrib={'count': str(len(self.steps))})
        tree = etree.ElementTree(root)
        xml_str = minidom.parseString(etree.tostring(tree.getroot())).toprettyxml()
        xml_str: str = xml_str.replace('<?xml version="1.0" ?>', '')
        return xml_str

    @property
    def descriptionSimple(self):
        """简单自我描述"""
        description = f'<CaseBox id="{id(self)}" caseNum="{self.caseNum}" level="{self.level}" flag="{self.flag}"/>'
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
    def label(self) -> Tuple[str, ...]:
        """获取用例tag"""
        # 用例类对象
        if isinstance(self.caseFunc, IBaseCase):
            return self.caseFunc.case_label
        # 用例类对象.run
        elif hasattr(self.caseFunc, '__self__') and isinstance(self.caseFunc.__self__, IBaseCase):
            return self.caseFunc.__self__.case_label
        # 用例函数
        elif hasattr(self.caseFunc, '_Decorate__decorators'):
            return tuple(map(lambda x: x.lower(), self.caseFunc._Decorate__decorators))
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
    def projectBox(self):
        """根项目盒子"""
        if self.__projectBox is None:
            return self.featureBox.projectBox
        return self.__projectBox

    @projectBox.setter
    def projectBox(self, projectBox: 'ProjectBox'):
        """设置根项目盒子"""
        self.__projectBox = projectBox

    @property
    def featureBox(self) -> Optional['FeatureBox']: return self.__featureBox  # 父级FeatureBox

    @featureBox.setter
    def featureBox(self, featureBox: 'FeatureBox'):
        """设置父级FeatureBox"""
        if not isinstance(featureBox, FeatureBox):
            self.toLog.error(f'只能设置 FeatureBox！')
            raise TypeError('只能设置 FeatureBox！')
        self.__featureBox = featureBox
        if self not in featureBox.caseBoxList and self.flag not in ('setup', 'teardown'):
            featureBox.addCaseBox(self)

    @property
    def locked(self): return self.__locked  # 是否属于独立执行的用例
    @property
    def toLog(self): return self.__toLog or self.projectBox.toLog  # 日志对象

    @toLog.setter
    def toLog(self, logger: Logger):
        """单独设置此用例的toLog日志对象"""
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__toLog = logger
        else:
            raise TypeError('logger 必须含有 info 和 error 方法！')

    @property
    def kfLog(self): return self.__kfLog or self.projectBox.kfLog  # 日志对象

    @kfLog.setter
    def kfLog(self, logger: Logger):
        """单独设置此用例的kfLog日志对象"""
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__kfLog = logger
        else:
            raise TypeError('logger 必须含有 info 和 error 方法！')

    @property
    def arguments(self): return self.projectBox.arguments  # 本次运行参数
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
        if level not in ('project', 'feature'):
            raise ValueError(f'`level` only can be `project` or `feature`, but not `{level}`!')
        self.__level = level

    @property
    def order(self):
        """执行次序，默认都是1"""
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
    def steps(self): return self.__steps  # 下级步骤盒子对象
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

    def getRunningStep(self) -> Optional[StepBox]:
        """获取正在执行的步骤"""
        for step in self.steps:
            if step.running == RunningStatus.Running:
                return step
        return None

    def getStepBoxByID(self, stepBoxID: int):
        """根据步骤盒ID获取步骤盒对象"""
        if not self.steps:
            return None
        stepBoxID = int(stepBoxID)
        for stepBox in self.steps:
            if stepBox.id == stepBoxID:
                return stepBox
        return None

    def addStepBox(self, *stepBox: StepBox):
        """添加步骤盒对象"""
        if not all(map(lambda c: isinstance(c, StepBox), stepBox)):
            self.toLog.error(f'本函数只能添加 StepBox！输入值：{stepBox}')
            raise TypeError('本函数只能添加 StepBox！')
        if not all(map(lambda c: c.caseBox is self or c.caseBox is None, stepBox)):
            self.toLog.error(f'只能添加本用例下的 StepBox！')
            raise TypeError('只能添加本用例下的 StepBox！')
        for _s in stepBox:
            if _s.caseBox is None:
                _s.caseBox = self
            if _s not in self.steps:
                self.__steps += (_s,)

    def getAttr(self, attrName: str):
        """从本用例载入后的对象中获取指定属性"""
        if self.module is None:
            return None
        try:
            return getattr(self.module, attrName)
        except Exception as err:
            self.toLog.error(f'无法从module获取属性：{attrName}，错误：{err}，用例盒子：{self}')
            raise AttributeError(err, f'无法从module获取属性：{attrName}，用例盒子：{self}')

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
            label = self.label
            if _untags:
                for untag in _untags.split(","):
                    if untag.lower() in label:
                        return False
            # 如果 taglist 中包含任意一个 tag, 则返回True
            if _tags:
                for tag in _tags.split(","):
                    if tag.lower() in label:
                        return True
            return False

        if tags:
            return tagRunMode(tags, untags)

        if self.projectBox.runBy == 'arguments':  # 通过tag判断是否执行
            tag = self.arguments['tag']
            untag = self.arguments.get('untag', '')
            return tagRunMode(tag, untag)
        elif self.projectBox.runBy == 'skip':  # 通过自身skip标记判断是否执行。setup/teardown不会跳过
            if self.skip and self.flag not in ('setup', 'teardown'):
                return False
            return True
        else:
            raise AttributeError(f"projectBox.runBy 意外值：{self.projectBox.runBy}")

    def willRun(self, *projectBox: 'ProjectBox') -> bool:
        """指定projectBox，通过读取当前运行用例，以及是否独立运行、是否允许插队，判断本用例是否将执行

        判断逻辑：
            - 用例运行前，首先 -> 读取当前运行的用例

            - 若无其他运行用例：**【执行本用例】**  *[END]*
            - 若有其他运行用例 -> 读取自身 `locked`

                - 若自身锁定：**【继续等待】**  *[END]*
                - 若自身不锁定 -> 读取该运行中的用例的 `locked`

                    - 若任一用例锁定，或自身无步骤：**【继续等待】**  *[END]*
                    - 若所有用例不锁定：**【执行本用例】**  *[END]*

        :param projectBox: 指定的projectBox
        :return: 本用例是否将执行
        """
        runningFuncBoxs = [caseBox for proBox in projectBox for caseBox in proBox.getRunningCaseBoxes()]
        if not runningFuncBoxs:  # 1. 若无其他运行用例：本用例将运行
            return True
        # 2. 若有其他运行用例：读取自身 `locked`
        if self.locked:  # 2.1. 若自身锁定：继续等待
            return False
        # 2.2. 若自身不锁定 -> 读取该运行中的用例的 `locked`
        # 2.2.1. 若任一用例锁定，或自身无步骤：继续等待
        if not self.steps or any([caseBox.locked for caseBox in runningFuncBoxs]):
            return False
        # 2.2.2. 若所有用例非独立执行：执行本用例
        return True

    def run(self):
        """执行这条用例（加入步骤只是方便管理，无论有无步骤都不影响。应该在用例内部实现stepBox的调用）

        示例::

            def step1Func(*args, **kwargs): return 10
            def step2Func(*args, **kwargs): ...

            def case():  # 内部自己实现步骤之间的复杂逻辑
                num = stepBox1.runStep(...)

                for _ in range(num):
                    stepBox2.runStep()

                return 0

            caseBox = CaseBox(case, featureBox=...)
            stepBox1 = StepBox(Step('步骤第一步'), step1Func, caseBox)
            stepBox2 = StepBox(Step('步骤第二步', 2), step2Func, caseBox)
            caseBox.run()

        :return: 是否通过
        """
        self.__running = RunningStatus.UnRun
        self.__isPass = None
        # 首先，判断是否应该执行
        if not self.shouldRun():
            if self.projectBox.runBy == 'skip':
                self.__running = RunningStatus.Skipped
            return self.isPass

        # 即将执行，预先判断其他用例运行情况
        self.__running = RunningStatus.Waiting
        self.__launchTime = datetime.datetime.now()
        if self.timeout == 0:
            if not self.willRun(self.projectBox):
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
                    willRun = self.willRun(self.projectBox)
                    if willRun:
                        break
                    self.toLog.info(f'用例：{self.caseNum} 等待其他执行中的用例执行完毕... 等待间隔：{self.frequency}s')
                    time.sleep(self.frequency)
                    usetime = time.time() - start
            except CaseStopCanceled:
                self.toLog.warning(f'用例：{self.caseNum} 等待中... 已取消')
                self.kfLog.warning(f'用例：{self.caseNum} 等待中... 已取消')
                self.__running = RunningStatus.Canceled
                self.__totalTime = datetime.datetime.now() - self.launchTime
                self.__totalTime_count += self.__totalTime
                return self.isPass
            except CaseStopExit:
                self.toLog.error(f'用例：{self.caseNum} 等待中... 退出执行！')
                self.kfLog.error(f'用例：{self.caseNum} 等待中... 退出执行！')
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
            if self.projectBox.kfLogMode in ('start', 'both'):
                self.kfLog.info(self.caseFullName)
            try:
                error_code = self.caseRunFunc()
                if not isinstance(error_code, int):
                    raise TypeError(f'用例函数定义应返回整数（0表示成功），然而实际返回为{type(error_code)}')
            except CaseStopCanceled:
                self.toLog.warning(f'用例：{self.caseNum} 执行中... 已取消')
                self.kfLog.warning(f'用例：{self.caseNum} 执行中... 已取消')
                self.__running = RunningStatus.Canceled
                return self.isPass
            except CaseStopExit:
                self.toLog.error(f'用例：{self.caseNum} 执行中... 退出执行！')
                self.kfLog.error(f'用例：{self.caseNum} 执行中... 退出执行！')
                self.__running = RunningStatus.Killed
                raise
            except Exception as err:
                err_msg = f'{err.__class__.__name__}: {err}\nAt: \n{traceback.format_exc().replace(str(pathlib.Path.cwd()), "")}'
                oneCaseLoopMsg.error = err_msg
                self.toLog.error(f'异常错误：{err_msg}')
                if self.projectBox.kfLogMode in ('end', 'both'):
                    self.kfLog.error(f'执行用例发生异常：{err_msg}')
                self.error_count += 1
                self.__running = RunningStatus.Error
                self.__isPass = False
                return self.isPass
            else:
                self.error_count += error_code
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
                oneCaseLoopMsg.stepErrors = tuple([f'Error in Step: [{stepBox.step}]\n-----\n{stepBox.error}'
                                                   for stepBox in self.steps if stepBox.error])
                self.__CaseStatus.loopMsgs += (oneCaseLoopMsg,)
                if self.projectBox.kfLogMode in ('end', 'both'):
                    if self.isPass is None:
                        self.kfLog.error(f"{self.caseFullName} *** failed! *** ---execute break---")
                    elif not self.isPass:
                        self.kfLog.error(f"{self.caseFullName} *** failed! ***")
                    elif self.isPass:
                        self.kfLog.info(f"{self.caseFullName} *** succeeded! ***")

        for i in range(self.loop):
            if self.loop > 1:
                self.kfLog.info(f'循环执行用例 *Loop[{i+1}/{self.loop}]*'.center(60, '-'))
            if not self.locked:  # 不锁定，不要求独立执行，则不需要线程锁
                main_run(OneCaseLoopMsg(loopIndex=i))
            with CaseBox.lock:
                main_run(OneCaseLoopMsg(loopIndex=i))
        return self.isPass


class FeatureBox:
    """一个业务功能分类盒对象(目录)，储存该业务功能分类下的所有用例函数对象，也可储存父级、子级功能分类对象"""

    def __init__(self, name: str, projectBox, *, parentFeatureBox=None, caseBoxList=None):
        """功能分类盒子，包括父/子功功能分类盒子、用例盒子列表

        * 执行前将会对用例进行重新排序再执行：按次序号升序、用例编号升序
        * 由于次序号默认都是 ``1``，所以默认情况下将按用例编号升序执行

        :param name: 功能分类名
        :param projectBox: 根项目盒子
        :param parentFeatureBox: 父级功能分类盒子，默认空
        :param caseBoxList: 所有下级用例盒子，默认空
        :type projectBox: ProjectBox
        :type parentFeatureBox: FeatureBox
        :type caseBoxList: List[CaseBox]
        """
        if parentFeatureBox is not None and not isinstance(parentFeatureBox, FeatureBox):
            self.toLog.error(f'父级只能是 FeatureBox！输入值：{parentFeatureBox}')
            raise TypeError('父级只能是 FeatureBox！')
        self.__feature_name: str = name
        self.__parent: FeatureBox = parentFeatureBox
        self.__children: Tuple[FeatureBox] = ()
        self.__caseBoxList: Tuple[CaseBox] = caseBoxList or ()
        self.__setup: CaseBox = None
        self.__teardown: CaseBox = None
        self.__projectBox = projectBox
        if self not in projectBox.featureBoxs:
            projectBox.addFeatureBox(self)

    def __str__(self): return self.descriptionFull
    def __repr__(self): return f'FeatureBox(name={self.dirName!r}, projectBox={self.projectBox!r})'

    @property
    def descriptionDetails(self):
        """最详细的自我描述"""
        xml_str = self.descriptionFull
        tree: etree._ElementTree = etree.ElementTree(etree.fromstring(xml_str))
        root: etree._Element = tree.getroot()
        setupEle: etree._Element = root.find('setup')
        teardownEle: etree._Element = root.find('teardown')
        childrenFeaturesEle: etree._Element = root.find('childrenFeatures')
        caseBoxListEle: etree._Element = root.find('caseBoxList')
        if self.setup:
            setupEle.clear()
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionDetails)).getroot())
        if self.teardown:
            teardownEle.clear()
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionDetails)).getroot())
        childrenFeaturesEle.clear()
        for featureBox in self.childrenFeatures:
            childrenFeaturesEle.append(etree.ElementTree(etree.fromstring(featureBox.descriptionDetails)).getroot())
        caseBoxListEle.clear()
        for caseBox in self.caseBoxList:
            case_tree = etree.ElementTree(etree.fromstring(caseBox.descriptionDetails))
            case_root: etree._Element = case_tree.getroot()
            case_root.set('caseNum', caseBox.caseNum)
            caseBoxListEle.append(case_root)

        new_xml = minidom.parseString(etree.tostring(tree.getroot()).replace(b'\n',b'').replace(b'\t',b'')).toprettyxml()
        new_xml: str = new_xml.replace('<?xml version="1.0" ?>', '')
        return new_xml

    @property
    def descriptionFull(self):
        """完整自我描述"""
        root = etree.Element('FeatureBox')  # 根节点
        etree.SubElement(root, 'id', attrib={'value': str(id(self))})
        etree.SubElement(root, 'featureName', attrib={'value': str(self.featureName)})
        parentFeatureEle = etree.SubElement(root, 'parentFeatureBox')
        etree.SubElement(root, 'childrenFeatures', attrib={'count': str(len(self.childrenFeatures))})
        setupEle = etree.SubElement(root, 'setup')
        teardownEle = etree.SubElement(root, 'teardown')
        caseBoxListEle = etree.SubElement(root, 'caseBoxList', attrib={'count': str(len(self.caseBoxList))})

        if self.parentFeatureBox:
            parentFeatureEle.append(etree.ElementTree(etree.fromstring(self.parentFeatureBox.descriptionSimple)).getroot())
        if self.setup:
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionSimple)).getroot())
        if self.teardown:
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionSimple)).getroot())
        for caseBox in self.caseBoxList:
            caseBoxListEle.append(etree.ElementTree(etree.fromstring(caseBox.descriptionSimple)).getroot())

        tree = etree.ElementTree(root)
        xml_str = minidom.parseString(etree.tostring(tree.getroot())).toprettyxml()
        xml_str: str = xml_str.replace('<?xml version="1.0" ?>', '')
        return xml_str

    @property
    def descriptionSimple(self):
        """简单自我描述"""
        return f'<FeatureBox id="{id(self)}" featureName="{self.featureName}" caseCount="{len(self.caseBoxList)}"/>'

    @property
    def projectBox(self): return self.__projectBox
    @property
    def featureName(self): return self.__feature_name  # 功能分类名(目录名)
    @property
    def dirName(self): return self.__feature_name  # 目录名(功能分类名)
    @property
    def parentFeatureBox(self) -> Optional['FeatureBox']: return self.__parent  # 父级功能分类对象
    @property
    def childrenFeatures(self): return self.__children  # 子级功能分类对象
    @property
    def caseBoxList(self): return self.__caseBoxList  # 所有用例盒对象
    @property
    def setup(self): return self.__setup  # setup用例函数盒子
    @property
    def teardown(self): return self.__teardown  # teardown用例函数盒子
    @property
    def toLog(self): return self.projectBox.toLog  # 日志对象
    @property
    def kfLog(self): return self.projectBox.kfLog  # 日志对象
    @property
    def arguments(self): return self.projectBox.arguments  # 本次运行参数

    def addChild(self, *childFeature):
        """添加子功能分类"""
        if not all(map(lambda c: isinstance(c, FeatureBox), childFeature)):
            self.toLog.error(f'子级功能分类只能是 FeatureBox！输入值：{childFeature}')
            raise TypeError('子级功能分类只能是 FeatureBox！')
        for _m in childFeature:
            if _m not in self.childrenFeatures:
                self.__children += (_m,)

    def addCaseFunc(self, *caseFunc, dirName=None):
        """储存用例对象

        :param dirName: 用例所在目录名
        :param caseFunc: 用例函数对象
        :type caseFunc: function
        :return:
        """
        for oneCaseFunc in caseFunc:
            if oneCaseFunc not in [cb.caseFunc for cb in self.caseBoxList]:
                self.__caseBoxList += (CaseBox(oneCaseFunc, featureBox=self, dirName=dirName),)

    def addCaseBox(self, *caseBox: CaseBox):
        """储存用例对象"""
        if not all(map(lambda c: isinstance(c, CaseBox), caseBox)):
            self.toLog.error(f'本函数只能添加 CaseBox！输入值：{caseBox}')
            raise TypeError('本函数只能添加 CaseBox！')
        if not all(map(lambda c: c.featureBox is None or c.featureBox is self, caseBox)):
            self.toLog.error(f'只能添加本功能分类下的 CaseBox！')
            raise TypeError('只能添加本功能分类下的 CaseBox！')
        for _cBox in caseBox:
            if _cBox.featureBox is None:
                _cBox.featureBox = self
            if _cBox not in self.caseBoxList and _cBox.flag not in ('setup', 'teardown'):
                self.__caseBoxList += (_cBox,)

    def getCaseBox(self, caseNum: str):
        """获取1个用例盒对象"""
        for caseBox in self.caseBoxList:
            if caseBox.caseNum == caseNum:
                return caseBox
        return None

    def setSetupCaseBox(self, setupCaseBox: CaseBox):
        """设置setup用例盒对象"""
        if not isinstance(setupCaseBox, CaseBox):
            self.toLog.error(f'本函数只能添加 CaseBox！输入值：{setupCaseBox}')
            raise TypeError('本函数只能添加 CaseBox！')
        setupCaseBox.flag = 'setup'
        setupCaseBox.featureBox = self
        setupCaseBox.dirName = self.dirName
        self.__setup = setupCaseBox

    def setSetupFunc(self, setupFunc, module):
        """设置setup用例函数

        :type setupFunc: function
        :type module: ModuleType
        """
        self.__setup = CaseBox(setupFunc, module, featureBox=self, flag='setup', dirName=self.dirName)

    def setTeardownCaseBox(self, teardownCaseBox: CaseBox):
        """设置teardown用例盒对象"""
        if not isinstance(teardownCaseBox, CaseBox):
            self.toLog.error(f'本函数只能添加 CaseBox！输入值：{teardownCaseBox}')
            raise TypeError('本函数只能添加 CaseBox！')
        teardownCaseBox.flag = 'teardown'
        teardownCaseBox.featureBox = self
        teardownCaseBox.dirName = self.dirName
        self.__teardown = teardownCaseBox

    def setTeardownFunc(self, teardownFunc, module):
        """设置teardown用例函数

        :type teardownFunc: function
        :type module: ModuleType
        """
        self.__teardown = CaseBox(teardownFunc, module, featureBox=self, flag='teardown', dirName=self.dirName)

    def getRunningCaseBox(self) -> List[CaseBox]:
        """获取当前功能分类正在执行的用例，无则返回空"""
        runningCases = []
        if self.setup is not None and self.setup.running == RunningStatus.Running:
            runningCases.append(self.setup)
        if self.teardown is not None and self.teardown.running == RunningStatus.Running:
            runningCases.append(self.teardown)
        for caseBox in self.caseBoxList:
            if caseBox.running == RunningStatus.Running:
                runningCases.append(caseBox)
        for childModule in self.childrenFeatures:
            runningCases += childModule.getRunningCaseBox()
        return runningCases

    def getWillRunCaseBoxes(self) -> List[CaseBox]:
        """获取此功能分类下应该执行的所有用例"""
        willRunCases = []
        for caseBox in self.caseBoxList:
            if caseBox.shouldRun():
                willRunCases.append(caseBox)
        for childModule in self.childrenFeatures:
            willRunCases += childModule.getWillRunCaseBoxes()
        return willRunCases

    def shouldRun(self, feature: str = None):
        """根据feature判断本功能分类是否执行"""
        return not feature or feature == self.featureName

    def countRunCase(self) -> int:
        """统计本功能分类有多少需执行的用例"""
        count = 0
        if self.projectBox.runBy == 'arguments':
            feature = self.arguments.get('feature')
            tag = self.arguments['tag']
            untag = self.arguments.get('untag', '')
            if not self.shouldRun(feature):
                return 0
            count += sum([c.shouldRun(tag, untag) for c in self.caseBoxList])
        elif self.projectBox.runBy == 'skip':
            count += sum([not c.skip for c in self.caseBoxList])
        for childFeature in self.childrenFeatures:
            count += childFeature.countRunCase()
        return count

    def sortCaseBoxList(self):
        """将 CaseBoxList 按执行顺序排序"""
        caseBoxList = list(self.caseBoxList)
        caseBoxList.sort(key=lambda b: b.caseNum)
        caseBoxList.sort(key=lambda b: b.order)
        self.__caseBoxList = tuple(caseBoxList)

    def run(self):
        """执行该功能分类的用例

        :return: 成功数、失败数
        """
        ok = no = 0
        case_run_count = self.countRunCase()
        if case_run_count == 0:
            return ok, no

        if self.setup is not None:
            self.kfLog.info('')
            self.kfLog.info(f' {self.featureName} Setup Start '.center(75, '-'))
            if not self.setup.run():
                return ok, no

        self.kfLog.info('')
        self.kfLog.info(' Test Start '.center(75, '-'))
        self.kfLog.info(f' start execute module: {self.featureName} '.center(75, '-'))
        self.sortCaseBoxList()
        for caseBox in self.caseBoxList:
            isPass = caseBox.run()
            if isPass is None:
                continue
            elif isPass:
                ok += 1
            else:
                no += 1
        for childFeatureBox in self.childrenFeatures:
            _ok, _no = childFeatureBox.run()
            ok += _ok
            no += _no
        if self.teardown is not None:
            self.kfLog.info('')
            self.kfLog.info(f' {self.featureName} Teardown Start '.center(75, '-'))
            self.teardown.run()
        return ok, no


class ProjectBox:
    """一个项目盒对象，包含所有功能分类、所有用例函数对象"""
    def __init__(self, projectPath: pathlib.Path, toLog=None, kfLog=None, *, kfLogMode='end', runBy='arguments'):
        """项目盒子，存储一个项目的所有功能分类、用例函数

        :param projectPath: 项目路径
        :param toLog: 用于记录简要和重要信息的日志对象，至少需提供 info、error两个方法。默认空。
        :param kfLog: 用于记录用例执行的日志对象，至少需提供 info、error两个方法。默认空。
        :param kfLogMode: kfLog在用例执行前后的记录模式：no-执行前后不记录，end-只记录执行完毕，start-只记录执行前，both-前后都记录
        :param runBy: 执行用例的筛选方式，arguments-通过赋值arguments，skip-通过用例skip属性
        """
        self.__projectPath = projectPath
        self.__featureBoxs: Tuple[FeatureBox] = ()
        self.__setup: CaseBox = None
        self.__teardown: CaseBox = None
        self.toLog = toLog
        self.kfLog = kfLog
        self.__kfLogMode = kfLogMode
        self.runBy = runBy
        self.__arguments = {}

    def __str__(self): return self.descriptionFull
    def __repr__(self): return f'ProjectBox(projectPath={self.projectPath!r})'

    @property
    def descriptionDetails(self):
        """最详细的自我描述，展示所有层级"""
        xml_str = self.descriptionFull
        tree: etree._ElementTree = etree.ElementTree(etree.fromstring(xml_str))
        root: etree._Element = tree.getroot()
        setupEle: etree._Element = root.find('setup')
        teardownEle: etree._Element = root.find('teardown')
        featureBoxsEle: etree._Element = root.find('featureBoxs')
        if self.setup:
            setupEle.clear()
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionDetails)).getroot())
        if self.teardown:
            teardownEle.clear()
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionDetails)).getroot())
        featureBoxsEle.clear()
        for feature in self.featureBoxs:
            feature_tree = etree.ElementTree(etree.fromstring(feature.descriptionDetails))
            feature_root: etree._Element = feature_tree.getroot()
            feature_root.set('featureName', feature.featureName)
            featureBoxsEle.append(feature_root)
        new_xml = minidom.parseString(etree.tostring(tree.getroot()).replace(b'\n',b'').replace(b'\t',b'')).toprettyxml()
        new_xml: str = new_xml.replace('<?xml version="1.0" ?>', '')
        return new_xml

    @property
    def descriptionFull(self):
        """完整自我描述"""
        root = etree.Element('ProjectBox')  # 根节点
        etree.SubElement(root, 'id', attrib={'value': str(id(self))})
        etree.SubElement(root, 'projectName', attrib={'value': str(self.projectName)})
        etree.SubElement(root, 'projectPath', attrib={'projectPath': str(self.projectPath)})
        setupEle = etree.SubElement(root, 'setup')
        teardownEle = etree.SubElement(root, 'teardown')
        featureBoxsEle = etree.SubElement(root, 'featureBoxs', attrib={'count': str(len(self.featureBoxs))})

        if self.setup:
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionSimple)).getroot())
        if self.teardown:
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionSimple)).getroot())
        for feature in self.featureBoxs:
            featureBoxsEle.append(etree.ElementTree(etree.fromstring(feature.descriptionSimple)).getroot())

        tree = etree.ElementTree(root)
        xml_str = minidom.parseString(etree.tostring(tree.getroot())).toprettyxml()
        xml_str: str = xml_str.replace('<?xml version="1.0" ?>', '')
        return xml_str

    @property
    def descriptionSimple(self):
        """简单自我描述"""
        feature_names = ';'.join([feature.featureName for feature in self.featureBoxs])
        return f'<ProjectBox id="{id(self)}" projectName="{self.projectName}" features="{feature_names}"/>'

    @property
    def kfLogMode(self): return self.__kfLogMode
    @property
    def featureBoxs(self): return self.__featureBoxs  # 所有功能分类盒对象
    @property
    def projectPath(self): return self.__projectPath  # 项目路径
    @property
    def projectName(self) -> str: return self.projectPath.name  # 项目名
    @property
    def setup(self) -> Optional[CaseBox]: return self.__setup  # setup用例函数盒子
    @property
    def teardown(self) -> Optional[CaseBox]: return self.__teardown  # teardown用例函数盒子

    @property
    def toLog(self) -> Logger:
        """用于记录简要和重要信息的日志对象"""
        if self.__toLog is not None:
            return self.__toLog
        return emptyLogger

    @property
    def kfLog(self) -> Logger:
        """用于记录用例执行的日志对象"""
        if self.__kfLog is not None:
            return self.__kfLog
        return emptyLogger

    @toLog.setter
    def toLog(self, logger: Logger):
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__toLog = logger
        else:
            raise TypeError('设置日志对象至少必须含有`info`和`error`方法！')

    @kfLog.setter
    def kfLog(self, logger: Logger):
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__kfLog = logger
        else:
            raise TypeError('设置日志对象至少必须含有`info`和`error`方法！')

    @property
    def runBy(self): return self.__runBy  # 执行用例的筛选方式

    @runBy.setter
    def runBy(self, runBy: str):
        """设置执行用例的筛选方式。arguments-通过赋值arguments，skip-通过用例skip属性"""
        if runBy not in ('arguments', 'skip'):
            raise ValueError('runBy 只能为 arguments/skip！')
        self.__runBy = runBy

    @property
    def arguments(self):
        """本次运行参数"""
        if not self.__arguments:
            raise ValueError('本次运行参数尚未设置！')
        return self.__arguments

    @arguments.setter
    def arguments(self, arguments: dict):
        """设置本次参数

        * arguments: 运行参数，未指定则类型都为str

            - project: 项目名，必须
            - tag: 指定tag，必须
            - serverIpAddress: 服务IP（一般为DCU IP），必须
            - untag: 排除tag，可选
            - feature: 功能分类名，可选
            - caseLoops: 指定用例循环次数，可选。``dict`` 格式::

                {
                    <featureName>: {
                        <caseNum>: 100,
                        <caseNum>: 50,
                        <caseNum>: 10,
                    }
                }
        """
        if not all(map(lambda x: bool(arguments.get(x)), ('project', 'tag', 'serverIpAddress'))):
            raise ValueError("'project', 'tag', 'serverIpAddress' are all needed!")
        self.__arguments = arguments
        caseLoops = arguments.get('caseLoops', {})
        if caseLoops:
            self.setCaseLoops(caseLoops)

    def setCaseLoops(self, caseLoops: dict):
        """指定用例循环次数，格式::

            {
                <featureName>: {
                    <caseNum>: 100,
                    <caseNum>: 50,
                    <caseNum>: 10,
                }
            }
        """
        if not caseLoops:
            return
        try:
            for featureName, caseLoopDic in caseLoops.items():
                for caseNum, loop in caseLoopDic.items():
                    featureBox = self.getFeatureBox(featureName)
                    if not featureBox:
                        continue
                    caseBox = featureBox.getCaseBox(caseNum)
                    if caseBox:
                        caseBox.loop = loop
        except Exception as err:
            raise ValueError('用例循环次数参数`caseLoops`有误！应为featureName下对应的用例编号的循环次数键值对！') from err

    def getFeatureBox(self, featureName: str):
        """获取一个 FeatureBox"""
        for featureBox in self.featureBoxs:
            if featureBox.featureName == featureName:
                return featureBox
        return None

    def addFeatureBox(self, *featureBox: FeatureBox):
        """添加功能分类盒对象"""
        if not all(map(lambda f: isinstance(f, FeatureBox), featureBox)):
            self.toLog.error(f'只能添加 FeatureBox！输入值：{featureBox}')
            raise TypeError('只能添加 FeatureBox！')
        if not all(map(lambda f: f.projectBox is self, featureBox)):
            self.toLog.error(f'只能添加相同根项目的 FeatureBox！')
            raise TypeError(f'只能添加相同根项目的 FeatureBox！')
        for _f in featureBox:
            if _f not in self.featureBoxs:
                self.__featureBoxs += (_f,)

    def setSetupCaseBox(self, setupCaseBox: CaseBox):
        """设置setup用例函数盒"""
        if not isinstance(setupCaseBox, CaseBox):
            self.toLog.error(f'只能设置 CaseBox！输入值：{setupCaseBox}')
            raise TypeError('只能设置 CaseBox！')
        setupCaseBox.projectBox = self
        setupCaseBox.level = 'project'
        setupCaseBox.flag = 'setup'
        self.__setup = setupCaseBox

    def setSetupFunc(self, setupFunc, module):
        """设置setup用例函数

        :type setupFunc: function
        :type module: ModuleType
        """
        self.__setup = CaseBox(setupFunc, module, projectBox=self, level='project', flag='setup')

    def setTeardownCaseBox(self, teardownCaseBox: CaseBox):
        """设置teardown用例函数盒"""
        if not isinstance(teardownCaseBox, CaseBox):
            self.toLog.error(f'只能设置 CaseBox！输入值：{teardownCaseBox}')
            raise TypeError('只能设置 CaseBox！')
        teardownCaseBox.projectBox = self
        teardownCaseBox.level = 'project'
        teardownCaseBox.flag = 'teardown'
        self.__teardown = teardownCaseBox

    def setTeardownFunc(self, teardownFunc, module):
        """设置teardown用例函数

        :type teardownFunc: function
        :type module: ModuleType
        """
        self.__teardown = CaseBox(teardownFunc, module, projectBox=self, level='project', flag='teardown')

    def getRunningCaseBoxes(self) -> List[CaseBox]:
        """获取当前所有正在运行的用例函数盒"""
        runningCaseBoxs = []
        if self.setup is not None and self.setup.running == RunningStatus.Running:
            runningCaseBoxs.append(self.setup)
        if self.teardown is not None and self.teardown.running == RunningStatus.Running:
            runningCaseBoxs.append(self.teardown)
        for featureBox in self.featureBoxs:
            runningCaseBoxs += featureBox.getRunningCaseBox()
        return runningCaseBoxs

    def getAllCaseStatus(self, exceptUnRun=False) -> AllCaseStatus:
        """获取当前项目所有用例的执行状态

        :param exceptUnRun: 是否排除未运行的用例，默认否
        :return: 所有用例的运行状态数据对象
        """
        all_status = AllCaseStatus()
        if self.setup is not None and self.setup.running == RunningStatus.Running:
            all_status.runningCases += (self.setup.CaseStatus,)
        if self.teardown is not None and self.teardown.running == RunningStatus.Running:
            all_status.runningCases += (self.teardown.CaseStatus,)
        for featureBox in self.featureBoxs:
            runningCases = featureBox.getRunningCaseBox()
            for oneCase in runningCases:
                all_status.runningCases += (oneCase.CaseStatus,)
            for caseBox in featureBox.caseBoxList:
                if caseBox.running == RunningStatus.UnRun and exceptUnRun:
                    continue
                all_status.allCases += (caseBox.CaseStatus,)
        return all_status

    def getAllWillRunCaseBoxes(self) -> List[CaseBox]:
        """获取所有将执行的用例函数盒"""
        willRunCaseBoxs = []
        for featureBox in self.featureBoxs:
            willRunCaseBoxs += featureBox.getWillRunCaseBoxes()
        willRunCaseBoxs.sort(key=lambda cb: cb.caseNum)
        willRunCaseBoxs.sort(key=lambda cb: cb.order)
        return willRunCaseBoxs

    def getCaseBoxByID(self, caseBoxID: int):
        """根据用例盒ID获取用例盒对象"""
        caseBoxID = int(caseBoxID)
        if self.setup and self.setup.id == caseBoxID:
            return self.setup
        if self.teardown and self.teardown.id == caseBoxID:
            return self.teardown
        for featureBox in self.featureBoxs:
            if featureBox.setup and featureBox.setup.id == caseBoxID:
                return featureBox.setup
            if featureBox.teardown and featureBox.teardown.id == caseBoxID:
                return featureBox.teardown
            for caseBox in featureBox.caseBoxList:
                if caseBox.id == caseBoxID:
                    return caseBox
        return None

    def run(self):
        """执行该项目的用例，运行后参数会清空

        :return: 通过数，不通过数
        """
        ok = no = 0
        feature = self.arguments.get('feature') if self.runBy == 'arguments' else None
        try:
            featureNames = [fb.featureName for fb in self.featureBoxs]
            case_run_count = sum([fb.countRunCase() for fb in self.featureBoxs])
            if feature and feature not in featureNames or case_run_count == 0:
                return ok, no
            if self.setup is not None:
                self.kfLog.info('')
                self.kfLog.info(' Project Setup Start '.center(75, '-'))
                setUpIsPass = self.setup.run()
                if not setUpIsPass:
                    return ok, no
            for childFeature in self.featureBoxs:
                _ok, _no = childFeature.run()
                ok += _ok
                no += _no
            if self.teardown is not None:
                self.kfLog.info('')
                self.kfLog.info(' Project Teardown Start '.center(75, '-'))
                self.teardown.run()
            return ok, no
        except CaseStopExit as err:
            self.toLog.error(f'已强制退出执行: CaseStopExit: {err}')

