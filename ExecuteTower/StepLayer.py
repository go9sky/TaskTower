# -*- coding: utf-8 -*-
# 创建时间:2025/7/1 23:03
# 创建人:天霄
# 基于 Python 3.11
# ========================================
# 用例步骤层级抽象类
# ========================================
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path
from typing import List, Tuple, Union, Optional, Callable, Dict, Any
from xml.dom import minidom
from lxml import etree

from .Step import Step
from .BaseType import *


class StepLayer:
    """一个管理用例函数中一个步骤的层级对象，储存关于该步骤的一些数据"""
    lock = threading.Lock()
    '''步骤的线程锁'''
    def __init__(self, step, stepFunc, caseLayer=None, *, locked=True, skip=False, timeout=0, frequency=15,
                 autoType='auto', failContinue=False):
        """加载步骤函数为抽象层级对象

        :param Step | str step: 步骤名
        :param Callable stepFunc: 步骤函数/类等可调用对象
        :param CaseLayer caseLayer: 父级用例函数层级
        :param bool locked: 是否锁定，默认是（是-必须没有其他运行中的锁定步骤时才能执行；否-视为闲置步骤，无视任何条件直接执行）
        :param bool skip: 是否跳过执行，默认否。
        :param int | float timeout: 在运行步骤前检查其他步骤状态、直到可运行的超时时间。（-1：永远，0：检查一次，>0：超时时间，秒）
        :param int | float frequency: 检查频率，秒
        :param str autoType: 自动化类型（no-auto:非自动，half-auto:半自动，auto:全自动）
        :param bool failContinue: 失败是否继续执行，默认否。当设置True时，失败将返回StepFailContinue这个错误
        """
        self.__running = RunningStatus.UnRun
        self.__isPass = None
        self.__step = step if isinstance(step, Step) else Step(step, parseFromMsg=True)
        self.__locked = locked
        self.__autoType = autoType
        self.__caseLayer = None
        self.__failContinue = failContinue
        self.error = None
        self.caseLayer = caseLayer
        self.stepFunc = stepFunc
        self.skip = skip
        self.timeout = timeout
        self.frequency = frequency
        if caseLayer and self not in self.caseLayer.steps:
            self.caseLayer.addStepLayer(self)

    def __str__(self): return self.descriptionFull
    def __repr__(self): return f'StepLayer(step={str(self.step)!r}, stepFunc={self.stepFunc!r})'

    @property
    def descriptionFull(self):
        """完整自我描述"""
        root = etree.Element('StepLayer')  # 根节点
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
        return f'<StepLayer id="{id(self)}" caseNum="{self.caseNum}" stepName="{self.stepName}" locked="{self.locked}"/>'

    @property
    def id(self): return id(self)
    @property
    def step(self) -> Step: return self.__step  # 步骤对象
    @property
    def stepName(self): return self.step.stepName  # 步骤名，如：step1、step3-2
    @property
    def caseNum(self): return self.caseLayer.caseNum
    @property
    def locked(self): return self.__locked  # 是否锁定
    @property
    def autoType(self): return self.__autoType  # 自动化类型
    @property
    def running(self) -> RunningStatus: return self.__running  # 当前执行状态（0-未运行，1-运行中，2-已结束运行且正常，3-已结束运行但存在异常）
    @property
    def isPass(self) -> Union[bool, None]: return self.__isPass  # 步骤是否通过（None-尚未执行完毕，True-通过，False-不通过）
    @property
    def toLog(self): return self.caseLayer.toLog  # 日志对象

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
    def caseLayer(self) -> CaseLayer: return self.__caseLayer  # 父级用例函数层级

    @caseLayer.setter
    def caseLayer(self, caseLayer: CaseLayer):
        """设置父级用例层级"""
        if self.__caseLayer is not None:
            raise ValueError('caseLayer 已存在值！不可覆盖！')
        if not isinstance(caseLayer, CaseLayer):
            raise TypeError(f'caseLayer 必须为 CaseLayer！输入值：{caseLayer}')
        self.__caseLayer = caseLayer
        if self not in caseLayer.steps:
            caseLayer.addStepLayer(self)

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

        :param runningCases: 运行中的用例层级集，默认读自所属用例的项目层级
        :type runningCases: list[CaseLayer]
        :return: 是否将执行
        """
        if not self.locked:  # 1. 若本步骤不锁定：执行本步骤
            return True
        # 2. 若本步骤锁定：-> 读取当前运行的步骤
        runningCases = runningCases or self.caseLayer.projectLayer.getRunningCaseLayers()
        runningStepLayers = [case.getRunningStep() for case in runningCases if case.getRunningStep() is not None]
        if not runningStepLayers:  # 2.1 若无其他运行步骤：执行本步骤
            return True
        # 2.2 若有其他运行步骤 -> 遍历其他步骤是否锁定。 只有其他步骤全部不锁定才判断将执行。
        for step in runningStepLayers:
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
                err_msg = f'{err.__class__.__name__}: {err}\nAt: \n{traceback.format_exc().replace(str(Path.cwd()), "")}'
                self.error = err_msg
                self.toLog.error(f'异常错误：{err_msg}')
                self.__running = RunningStatus.Error
                self.__isPass = False
                if not self.__failContinue:
                    raise
                self.caseLayer.error_count += 1
                return StepFailContinue(err)
            else:
                self.__running = RunningStatus.Finished
                self.__isPass = True
                return result

        if not self.locked:  # 闲置步骤则不需要线程锁
            return main_runStep()
        with StepLayer.lock:
            return main_runStep()


from .CaseLayer import CaseLayer