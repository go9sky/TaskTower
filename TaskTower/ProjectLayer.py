# -*- coding: utf-8 -*-
# 创建时间:2025/7/1 23:04
# 创建人:天霄
# 基于 Python 3.11
# ========================================
# 以业务为中心，将项目、业务功能分类、用例、用例步骤各自抽象定义为一个层级进行管理
# ========================================
from __future__ import annotations

from pathlib import Path
from logging import Logger
from types import ModuleType
from typing import List, Tuple, Union, Optional, Callable, Dict, Any
from xml.dom import minidom
from lxml import etree

from .BaseType import *

__all__ = ['ProjectLayer', 'FeatureLayer', 'CaseLayer', 'RunningStatus']


class ProjectLayer:
    """一个项目层对象，包含所有功能分类、所有用例函数对象"""
    def __init__(self, projectPath: Path, toLog:Logger=None, dtLog:Logger=None, *, dtLogMode='end', runBy='skip'):
        """项目层级，存储一个项目的所有功能分类、用例函数

        :param projectPath: 项目路径
        :param toLog: 用于记录简要和重要信息的日志对象。默认空。
        :param dtLog: 用于记录用例执行详情的日志对象。默认空。`dt` 是 `detail` 的简写。
        :param dtLogMode: dtLog在用例执行前后的记录模式：no-执行前后不记录，end-只记录执行完毕，start-只记录执行前，both-前后都记录
        :param runBy: 执行用例的筛选方式，arguments-通过赋值arguments，skip-通过用例skip属性
        """
        self.__projectPath = projectPath
        self.__featureLayers: Tuple[FeatureLayer, ...] = ()
        self.__setup: CaseLayer | None = None
        self.__teardown: CaseLayer | None = None
        self.toLog = toLog
        self.dtLog = dtLog
        self.__dtLogMode = dtLogMode
        self.runBy = runBy
        self.__arguments = {}

    def __str__(self): return self.descriptionFull
    def __repr__(self): return f'ProjectLayer(projectPath={self.projectPath!r})'

    @property
    def descriptionDetails(self):
        """最详细的自我描述，展示所有层级"""
        xml_str = self.descriptionFull
        tree: etree._ElementTree = etree.ElementTree(etree.fromstring(xml_str))
        root: etree._Element = tree.getroot()
        setupEle: etree._Element = root.find('setup')
        teardownEle: etree._Element = root.find('teardown')
        featureLayersEle: etree._Element = root.find('featureLayers')
        if self.setup:
            setupEle.clear()
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionDetails)).getroot())
        if self.teardown:
            teardownEle.clear()
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionDetails)).getroot())
        featureLayersEle.clear()
        for feature in self.featureLayers:
            feature_tree = etree.ElementTree(etree.fromstring(feature.descriptionDetails))
            feature_root: etree._Element = feature_tree.getroot()
            feature_root.set('featureName', feature.featureName)
            featureLayersEle.append(feature_root)
        new_xml = minidom.parseString(etree.tostring(tree.getroot()).replace(b'\n',b'').replace(b'\t',b'')).toprettyxml()
        new_xml: str = new_xml.replace('<?xml version="1.0" ?>', '')
        return new_xml

    @property
    def descriptionFull(self):
        """完整自我描述"""
        root = etree.Element('ProjectLayer')  # 根节点
        etree.SubElement(root, 'id', attrib={'value': str(id(self))})
        etree.SubElement(root, 'projectName', attrib={'value': str(self.projectName)})
        etree.SubElement(root, 'projectPath', attrib={'projectPath': str(self.projectPath)})
        setupEle = etree.SubElement(root, 'setup')
        teardownEle = etree.SubElement(root, 'teardown')
        featureLayerEle = etree.SubElement(root, 'featureLayers', attrib={'count': str(len(self.featureLayers))})

        if self.setup:
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionSimple)).getroot())
        if self.teardown:
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionSimple)).getroot())
        for feature in self.featureLayers:
            featureLayerEle.append(etree.ElementTree(etree.fromstring(feature.descriptionSimple)).getroot())

        tree = etree.ElementTree(root)
        xml_str = minidom.parseString(etree.tostring(tree.getroot())).toprettyxml()
        xml_str: str = xml_str.replace('<?xml version="1.0" ?>', '')
        return xml_str

    @property
    def descriptionSimple(self):
        """简单自我描述"""
        feature_names = ';'.join([feature.featureName for feature in self.featureLayers])
        return f'<ProjectLayer id="{id(self)}" projectName="{self.projectName}" features="{feature_names}"/>'

    @property
    def dtLogMode(self): return self.__dtLogMode
    @property
    def featureLayers(self): return self.__featureLayers  # 所有功能分类层对象
    @property
    def projectPath(self): return self.__projectPath  # 项目路径
    @property
    def projectName(self) -> str: return self.projectPath.name  # 项目名
    @property
    def setup(self) -> Optional[CaseLayer]: return self.__setup  # setup用例函数层级
    @property
    def teardown(self) -> Optional[CaseLayer]: return self.__teardown  # teardown用例函数层级

    @property
    def toLog(self) -> Logger:
        """用于记录简要和重要信息的日志对象，应仅用于扼要信息记录"""
        return self.__toLog if self.__toLog is not None else emptyLogger

    @property
    def dtLog(self) -> Logger:
        """用于记录用例执行详情的日志对象，可用于外部调用"""
        return self.__dtLog if self.__dtLog is not None else emptyLogger

    @toLog.setter
    def toLog(self, logger: Logger):
        """用于记录简要和重要信息的日志对象，应仅用于扼要信息记录"""
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__toLog = logger
        else:
            raise TypeError('设置日志对象至少必须含有`info`和`error`方法！')

    @dtLog.setter
    def dtLog(self, logger: Logger):
        """用于记录用例执行详情的日志对象，可用于外部调用"""
        if hasattr(logger, 'info') and hasattr(logger, 'error') or logger is None:
            self.__dtLog = logger
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
                    featureLayer = self.getFeatureLayer(featureName)
                    if not featureLayer:
                        continue
                    caseLayer = featureLayer.getCaseLayer(caseNum)
                    if caseLayer:
                        caseLayer.loop = loop
        except Exception as err:
            raise ValueError('用例循环次数参数`caseLoops`有误！应为featureName下对应的用例编号的循环次数键值对！') from err

    def getFeatureLayer(self, featureName: str):
        """获取一个 FeatureLayer"""
        for featureLayer in self.featureLayers:
            if featureLayer.featureName == featureName:
                return featureLayer
        return None

    def addFeatureLayer(self, *featureLayer: FeatureLayer):
        """添加功能分类层对象"""
        if not all(map(lambda f: isinstance(f, FeatureLayer), featureLayer)):
            self.toLog.error(f'只能添加 FeatureLayer！输入值：{featureLayer}')
            raise TypeError('只能添加 FeatureLayer！')
        if not all(map(lambda f: f.projectLayer is self, featureLayer)):
            self.toLog.error(f'只能添加相同根项目的 FeatureLayer！')
            raise TypeError(f'只能添加相同根项目的 FeatureLayer！')
        for _f in featureLayer:
            if _f not in self.featureLayers:
                self.__featureLayers += (_f,)

    def setSetupCaseLayer(self, setupCaseLayer: CaseLayer):
        """设置setup用例函数层"""
        if not isinstance(setupCaseLayer, CaseLayer):
            self.toLog.error(f'只能设置 CaseLayer！输入值：{setupCaseLayer}')
            raise TypeError('只能设置 CaseLayer！')
        setupCaseLayer.projectLayer = self
        setupCaseLayer.level = 'project'
        setupCaseLayer.flag = 'setup'
        self.__setup = setupCaseLayer

    def setSetupFunc(self, setupFunc, module):
        """设置setup用例函数

        :type setupFunc: function
        :type module: ModuleType
        """
        self.__setup = CaseLayer(setupFunc, module, projectLayer=self, level='project', flag='setup')

    def setTeardownCaseLayer(self, teardownCaseLayer: CaseLayer):
        """设置teardown用例函数层"""
        if not isinstance(teardownCaseLayer, CaseLayer):
            self.toLog.error(f'只能设置 CaseLayer！输入值：{teardownCaseLayer}')
            raise TypeError('只能设置 CaseLayer！')
        teardownCaseLayer.projectLayer = self
        teardownCaseLayer.level = 'project'
        teardownCaseLayer.flag = 'teardown'
        self.__teardown = teardownCaseLayer

    def setTeardownFunc(self, teardownFunc, module):
        """设置teardown用例函数

        :type teardownFunc: function
        :type module: ModuleType
        """
        self.__teardown = CaseLayer(teardownFunc, module, projectLayer=self, level='project', flag='teardown')

    def getRunningCaseLayers(self) -> List[CaseLayer]:
        """获取当前所有正在运行的用例函数层"""
        runningCaseLayers = []
        if self.setup is not None and self.setup.running == RunningStatus.Running:
            runningCaseLayers.append(self.setup)
        if self.teardown is not None and self.teardown.running == RunningStatus.Running:
            runningCaseLayers.append(self.teardown)
        for featureLayer in self.featureLayers:
            runningCaseLayers += featureLayer.getRunningCaseLayer()
        return runningCaseLayers

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
        for featureLayer in self.featureLayers:
            runningCases = featureLayer.getRunningCaseLayer()
            for oneCase in runningCases:
                all_status.runningCases += (oneCase.CaseStatus,)
            for caseLayer in featureLayer.caseLayerList:
                if caseLayer.running == RunningStatus.UnRun and exceptUnRun:
                    continue
                all_status.allCases += (caseLayer.CaseStatus,)
        return all_status

    def getAllWillRunCaseLayers(self) -> List[CaseLayer]:
        """获取所有将执行的用例函数层"""
        willRunCaseLayers = []
        for featureLayer in self.featureLayers:
            willRunCaseLayers += featureLayer.getWillRunCaseLayers()
        willRunCaseLayers.sort(key=lambda cb: cb.caseNum)
        willRunCaseLayers.sort(key=lambda cb: cb.order)
        return willRunCaseLayers

    def getCaseLayerByID(self, caseLayerID: int):
        """根据用例层ID获取用例层对象"""
        caseLayerID = int(caseLayerID)
        if self.setup and self.setup.id == caseLayerID:
            return self.setup
        if self.teardown and self.teardown.id == caseLayerID:
            return self.teardown
        for featureLayer in self.featureLayers:
            if featureLayer.setup and featureLayer.setup.id == caseLayerID:
                return featureLayer.setup
            if featureLayer.teardown and featureLayer.teardown.id == caseLayerID:
                return featureLayer.teardown
            for caseLayer in featureLayer.caseLayerList:
                if caseLayer.id == caseLayerID:
                    return caseLayer
        return None

    def run(self):
        """执行该项目的用例，运行后参数会清空

        :return: 通过数，不通过数
        """
        ok = no = 0
        feature = self.arguments.get('feature') if self.runBy == 'arguments' else None
        try:
            featureNames = [fb.featureName for fb in self.featureLayers]
            case_run_count = sum([fb.countRunCase() for fb in self.featureLayers])
            if feature and feature not in featureNames or case_run_count == 0:
                return ok, no
            if self.setup is not None:
                self.dtLog.info('')
                self.dtLog.info(' Project Setup Start '.center(75, '-'))
                setUpIsPass = self.setup.run()
                if not setUpIsPass:
                    return ok, no
            for childFeature in self.featureLayers:
                _ok, _no = childFeature.run()
                ok += _ok
                no += _no
            if self.teardown is not None:
                self.dtLog.info('')
                self.dtLog.info(' Project Teardown Start '.center(75, '-'))
                self.teardown.run()
            return ok, no
        except CaseStopExit as err:
            self.toLog.error(f'已强制退出执行: CaseStopExit: {err}')


from .FeatureLayer import FeatureLayer
from .CaseLayer import CaseLayer
