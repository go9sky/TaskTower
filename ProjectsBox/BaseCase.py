# -*- coding: utf-8 -*-
# 创建日期：2024/5/21
# 作者：天霄
# 简介：基础管理用例相关的类。根据项目需要可调整
import datetime
import functools
import os
import pathlib
import re
import time
from abc import abstractmethod
from types import ModuleType
from typing import Tuple, Callable, Union

from .BaseType import IBaseCase
from .ProjectBox import CaseBox, StepBox
from .Step import Step

# from comm_func import WithStep, kfLog
# from comm_func.KFExceptions import KFException, KFStepFailedError


class BaseCase(IBaseCase):
    """用例对象基类，必须重定义、属性，必须重写init、run方法。

    - 必须重定义属性：`case_num`、`case_title`
    - 必须重写方法：`init`、`run`
    - 若不在 `init` 方法中通过 `self.setSelf(...)` 设置自我属性，则默认相当于 `self.setSelf(self.run)`

    继承示例::

        class MyCase001(BaseCase):
            case_num = 'my_case_001'
            case_title = '我的用例001'

            def init(self):
                self.setSelf(self.run, featureBox=featureBox)
                self.step1 = self.addStepBox("step1: 选择电表", func1)
                self.step2 = self.addStepBox("step2: 连接电表", func2)
                self.step3 = self.addStepBox("step3: 断开电表", func3)

            def run(self):
                meterNum = self.step1.runStep()
                conn = self.step2.runStep(meterNum)
                self.step3.runStep(conn)
                return 0

        case = MyCase001()
        case.run()

    """
    case_num = ''
    case_title = ''
    case_label: Tuple[str, ...] = ()  # 用例标签，可选重写。特殊：setup、teardown 标签被视为非用例

    exe_case_id = 0  # 用例执行id
    caseBox: CaseBox = None
    stepBoxs: Tuple[StepBox] = ()
    __all_case_num = set()

    @abstractmethod
    def init(self):
        raise NotImplementedError(f"必须重写`init`方法！子类：`{self.__class__.__name__}` in `{self.file}`")

    @abstractmethod
    def run(self):
        raise NotImplementedError(f"必须重写`run`方法！子类：`{self.__class__.__name__}` in `{self.file}`")

    def __init_subclass__(cls, **kwargs):
        """子类定义检查：必须定义类属性：case_num、case_title"""
        cls.isCase = not any(map(lambda x: x in cls.case_label, ('setup', 'teardown')))
        file = pathlib.Path(cls.__module__.replace('.', os.sep) + '.py')
        cls.file = file
        cls.dirname = file.parent.name
        if not cls.case_num:
            raise NotImplementedError(f"未定义类属性`case_num`！子类：`{cls.__name__}` in `{file}`")
        if not cls.case_title:
            raise NotImplementedError(f"未定义类属性`case_title`！子类：`{cls.__name__}` in `{file}`")
        cls_dict = cls.__dict__
        if 'stepBoxs' in cls_dict:
            raise PermissionError(f"禁止重新定义属性`stepBoxs`！子类：`{cls.__name__}` in `{file}`")
        if 'caseBox' in cls_dict:
            raise PermissionError(f"禁止在类属性上重新定义`caseBox`，请通过重写`init`方法赋值！子类：`{cls.__name__}` in `{file}`")
        if '__init__' in cls_dict:
            raise PermissionError(f"禁止重写`__init__`方法！子类：`{cls.__name__}` in `{file}`")
        if 'addStepBox' in cls_dict:
            raise PermissionError(f"禁止重写`addStepBox`方法！子类：`{cls.__name__}` in `{file}`")
        if 'getStepBox' in cls_dict:
            raise PermissionError(f"禁止重写`getStepBox`方法！子类：`{cls.__name__}` in `{file}`")
        if 'at_step' in cls_dict:
            raise PermissionError(f"禁止重写`at_step`方法！子类：`{cls.__name__}` in `{file}`")
        cls.case_full_name = f"TestCase: {cls.case_num}, {cls.case_title}"
        if cls.case_num not in ('setup', 'teardown'):
            if cls.case_num in BaseCase.__all_case_num:
                raise AttributeError(f"类属性`case_num`存在重复值！子类：`{cls.__name__}` in `{file}`")
            BaseCase.__all_case_num.add(cls.case_num)

    def __init__(self):
        self.__teardownFunctions = ()
        self.lastTeardownStep = None
        self.successMsg = ''  # 执行成功后的附加信息
        self.failMsg = ''  # 执行失败后的附加信息
        self.init()
        self.caseBox.kfLog = kfLog.kfLog

    def at_step(self, stepBox: StepBox) -> StepBox:
        """装饰步骤盒的步骤函数，在步骤前后执行数据库记录更新；在可传递的情况下传递自身exLog参数"""
        func = stepBox.stepFunc

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with stepBox.withStep():
                try:
                    result = func(*args, **kwargs)
                    return result
                except KFException as e:
                    kfLog.kfLog.error(f'步骤失败：【{stepBox.step}】，问题：【{e.__class__.__name__}: {e}】')
                    raise KFStepFailedError(str(stepBox.step), f'执行步骤失败，问题：{e}') from e

        stepBox.stepFunc = wrapper
        stepBox.step.logger = kfLog.kfLog
        return stepBox

    def setCaseBox(self, module: ModuleType = None, *, featureBox=None, projectBox=None,
                   level='feature', flag=None, dirName=None, locked=True, skip=True, timeout=0, frequency=15):
        """设置自身用例属性

        :param module: 用例函数所在.py文件对象
        :param featureBox: 父级业务功能模块盒子
        :param projectBox: 根项目盒子
        :param level: 用例级别，默认模块级（project/feature）
        :param flag: 特殊标记：setup、teardown（这两个flag必定执行）
        :param dirName: 所在模块目录名，当传入featureBox时以其为准。
        :param skip: 是否跳过，默认是。（仅 `projectBox.runBy="skip"` 有效）
        :param locked: 是否锁定，默认是（是-本用例只能独立运行，不允许任何用例同时并行；否-反之，若运行中的用例全部不锁定才可运行）
        :param timeout: 在执行用例前检查其他用例状态、直到可运行的超时时间。（-1：永远，0：检查一次，>0：超时时间，秒）
        :param frequency: 检查频率，秒

        :type module: ModuleType
        :type featureBox: FeatureBox
        :type projectBox: ProjectBox
        :type level: str
        :type flag: str
        :type dirName: str
        """
        self.caseBox = CaseBox(self.run, module, featureBox=featureBox, projectBox=projectBox, level=level,
                               flag=flag, dirName=dirName, locked=locked, skip=skip, timeout=timeout,
                               frequency=frequency)
        return self.caseBox

    @property
    def teardownFunctions(self):
        """获取teardown函数列表

        :return: teardown函数列表
        :rtype: tuple[function]
        """
        return self.__teardownFunctions

    def addTeardown(self, func, description=''):
        """添加teardown函数

        :param func: teardown函数
        :param description: 步骤描述
        :type func: function
        """
        if not self.lastTeardownStep:
            self.lastTeardownStep = Step(description)
        else:
            self.lastTeardownStep = self.lastTeardownStep.nextStep(description)
        nowStep = str(self.lastTeardownStep)

        @functools.wraps(func)
        def teardownStepFunc(*args, **kwargs):
            with WithStep(nowStep):
                return func(*args, **kwargs)
        self.__teardownFunctions += (teardownStepFunc,)

    def __call__(self):
        return self.run()

    def addStepBox(self, step, stepFunc, locked=True, timeout=0, frequency=15, autoType='auto', failContinue=False) -> StepBox:
        """添加步骤盒

        :param step: 步骤名，Step对象或str描述
        :param stepFunc: 步骤对应的函数
        :param locked: 该步骤是否锁定，默认是（是-必须没有其他运行中的锁定步骤时才能执行；否-视为闲置步骤，无视任何条件直接执行）
        :param timeout: 在运行步骤前检查其他步骤状态、直到可运行的超时时间。（-1：永远，0：检查一次，>0：超时时间，秒）
        :param frequency: 检查频率，秒
        :param autoType: 自动化类型（no-auto:非自动，half-auto:半自动，auto:全自动）
        :param failContinue: 失败是否继续下一步，默认否
        :type step: Step | str
        :type stepFunc: function
        :return: StepBox对象
        """
        if not self.caseBox:
            self.setCaseBox()
        step = step if isinstance(step, Step) else Step(step, parseFromMsg=True)
        if step.stepName in [sBox.stepName for sBox in self.stepBoxs]:
            raise ValueError(f'步骤名重复：{step.stepName}')
        stepBox = StepBox(step, stepFunc, self.caseBox, locked=locked, timeout=timeout, frequency=frequency,
                          autoType=autoType, failContinue=failContinue)
        stepBox = self.at_step(stepBox)
        self.stepBoxs += (stepBox,)
        return stepBox

    def getStepBox(self, step: Step):
        """获取步骤盒"""
        for stepBox in self.stepBoxs:
            if stepBox.step == step:
                return stepBox
        return None

    def duringDoing(self, doFunc: Callable, days: Union[int, float], atTime: Union[str, datetime.time]):
        """持续几天，每天定时执行一个函数

        :param doFunc: 函数对象
        :param days: 超时时间，天
        :param atTime: 定时的时间字符串，精确到秒
        :return:
        """
        if isinstance(atTime, str):
            match = re.match(r'^(\d+):(\d+):(\d+)$', atTime)
            if not match:
                raise TypeError(f'时间格式不正确（须精确到秒）：{atTime}')
            targetTime = datetime.datetime(1, 1, 2, int(match.group(1)), int(match.group(2)), int(match.group(3)))
        else:
            targetTime = datetime.datetime(1, 1, 2).replace(hour=atTime.hour, minute=atTime.minute, second=atTime.second)
        closeTo = targetTime - datetime.timedelta(minutes=1)
        start = datetime.datetime.now()
        frequency = 45
        while (now := datetime.datetime.now()) - start < datetime.timedelta(days=days):
            if now.hour == targetTime.hour and now.minute == targetTime.minute and now.second == targetTime.second:
                kfLog.kfLog.info(f'到达指定时间 {atTime}，开始定时执行')
                doFunc()
                frequency = 45
            elif now.hour == closeTo.hour and now.minute == closeTo.minute:
                frequency = 0.6
            time.sleep(frequency)

