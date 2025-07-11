# -*- coding: utf-8 -*-
# 创建日期：2024/7/29
# 作者：天霄
# 简介：项目加载器与用例基类的基本类型
import datetime
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Tuple
from pydantic import BaseModel, Field

__all__ = ['simpleLog', 'RunningStatus', 'IBaseCase', 'baseConfig', 'Enums', 'emptyLogger',
           'StepFailContinue', 'CaseStopCanceled', 'CaseStopExit',
           'SkippedError', 'ExecuteClashError', 'ExecuteTimeoutError',
           'StepFailedError',
           'OneCaseLoopMsg', 'OneCaseStatus', 'AllCaseStatus']


def simpleLog(name: str, logLevel=20):
    """生成一个简单的仅输出到控制台的日志对象"""
    logger = logging.getLogger(name)
    logger.setLevel(logLevel)
    fmt = f"[{name:<12}][%(levelname)-7s] %(message)s"
    formatter = logging.Formatter(fmt)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)
    logger.addHandler(streamHandler)
    return logger


class RunningStatus(Enum):
    """运行状态枚举值"""
    UnRun = 0     # 尚未执行
    Running = 1   # 执行中
    Finished = 2  # 执行结束且正常
    Error = 3     # 执行结束但异常
    Skipped = 4   # 已跳过执行，当runBy=skip时才会出现
    Waiting = 5     # 用例多线程执行时才会出现。等待中，等待其他执行用例/步骤执行完毕
    Timeout = 6     # 用例多线程执行时才会出现。等待超时
    Canceled = 7   # 用例多线程执行时才会出现。已取消，在等待中或执行中时被取消执行
    Killed = 8   # 已中断程序，对于用户终止程序或系统终止程序时出现的情况，如Ctrl+C。但注意：无法捕获所有情况，如系统级崩溃、断电等


class IBaseCase(ABC):
    """用例对象基类接口，仅用于定义基本接口"""
    case_num: str         # 用例编号
    case_title: str       # 用例标题
    case_full_name: str   # 标准格式用例全称（含编号、标题，及前缀中缀后缀的格式化名称）
    case_tag: Tuple[str, ...]  # 用例自定义标签
    @abstractmethod
    def run(self): ...


@dataclass(frozen=True)
class _Enums:
    """固定枚举值"""
    RunBy_skip = 'skip'
    RunBy_arguments = 'arguments'

    DtLogMode_no = 'no'
    DtLogMode_end = 'end'
    DtLogMode_start = 'start'
    DtLogMode_both = 'both'

    Level_project = 'project'
    Level_feature = 'feature'

    Flag_setup = 'setup'
    Flag_teardown = 'teardown'


@dataclass
class _BaseConfigs:
    """TaskTower 全局配置"""
    closeWarning = False
    '''是否关闭警告'''

    successFlag = 0
    '''用例函数执行返回值中，代表执行成功的值。其他执行结果也应该返回同类型值。'''

    tagAttributeName = ''
    '''待装载用例对象中，用于存储自定义标签的属性名，默认无'''


baseConfig = _BaseConfigs()
Enums = _Enums()
emptyLogger = simpleLog('TowerLogger')


class StepFailContinue(Exception):  """步骤失败但继续的错误"""
class CaseStopCanceled(Exception):  """取消当前执行用例时应抛出的错误类型"""
class CaseStopExit(Exception):  """退出所有用例执行时应抛出的错误类型"""


class SkippedError(Exception):  """错误：已跳过"""
class ExecuteClashError(Exception):  """错误：执行冲突"""
class ExecuteTimeoutError(Exception):  """错误：执行等待超时"""

class StepFailedError(Exception):  """错误：执行步骤失败"""


# =========数据结构定义==========
class OneCaseLoopMsg(BaseModel):
    """一条用例一次循环的信息"""
    loopIndex: int   # 循环次序索引，0是第一次
    isPass: bool | None = None  # 是否通过
    duration: datetime.timedelta = datetime.timedelta()  # 纯粹用例耗时
    error: str = ''  # 异常信息
    stepErrors: tuple[str, ...] = ()  # 子步骤的错误


class OneCaseStatus(BaseModel):
    """一个用例的执行状态等信息"""
    caseNum: str  # 用例编号
    caseTitle: str = ''  # 用例标题
    level: str = 'project'  # 级别 feature/project
    featureName: str | None = None  # 功能模块名
    running: RunningStatus = RunningStatus.UnRun
    isPass: bool | None = None  # 用例执行是否通过 （只计最后一次循环）
    duration: datetime.timedelta = datetime.timedelta()  # 纯粹用例耗时（计最后一次循环）
    totalTime: datetime.timedelta = datetime.timedelta()  # 完整执行用例耗时，多线程执行时与前者的区别就是包括了前置等待时间（计最后一次循环）
    runCount: int = 0
    loopMsgs: tuple[OneCaseLoopMsg, ...] = ()


class AllCaseStatus(BaseModel):
    """一个项目的所有执行状态"""
    runningCases: tuple[OneCaseStatus, ...] = ()
    allCases: tuple[OneCaseStatus, ...] = ()


