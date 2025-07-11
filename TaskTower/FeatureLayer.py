# -*- coding: utf-8 -*-
# 创建时间:2025/7/1 23:01
# 创建人:天霄
# 基于 Python 3.11
# ========================================
# 业务功能分类层级抽象类
# ========================================
from __future__ import annotations

from types import ModuleType
from typing import List, Tuple, Union, Optional, Callable, Dict, Any
from xml.dom import minidom
from lxml import etree

from .BaseType import *

class FeatureLayer:
    """一个业务功能分类层级对象(目录)，储存该业务功能分类下的所有用例函数对象，也可储存父级、子级功能分类对象"""

    def __init__(self, name: str, projectLayer, *, parentFeatureLayer=None, caseLayerList=None):
        """功能分类层级，包括父/子功功能分类层级、用例层级列表

        * 执行前将会对用例进行重新排序再执行：按次序号升序、用例编号升序
        * 由于次序号默认都是 ``1``，所以默认情况下将按用例编号升序执行

        :param str name: 功能分类名
        :param ProjectLayer projectLayer: 根项目层级
        :param FeatureLayer parentFeatureLayer: 父级功能分类层级，默认空
        :param List[CaseLayer] caseLayerList: 所有下级用例层级，默认空
        """
        if parentFeatureLayer is not None and not isinstance(parentFeatureLayer, FeatureLayer):
            self.toLog.error(f'父级只能是 FeatureLayer！输入值：{parentFeatureLayer}')
            raise TypeError('父级只能是 FeatureLayer！')
        self.__feature_name: str = name
        self.__parent: FeatureLayer = parentFeatureLayer
        self.__children: Tuple[FeatureLayer, ...] = ()
        self.__caseLayerList: Tuple[CaseLayer, ...] = caseLayerList and tuple(caseLayerList) or ()
        self.__setup: CaseLayer | None = None
        self.__teardown: CaseLayer | None = None
        self.__projectLayer = projectLayer
        if self not in projectLayer.featureLayers:
            projectLayer.addFeatureLayer(self)

    def __str__(self): return self.descriptionFull
    def __repr__(self): return f'FeatureLayer(name={self.dirName!r}, projectLayer={self.projectLayer!r})'

    @property
    def descriptionDetails(self):
        """最详细的自我描述"""
        xml_str = self.descriptionFull
        tree: etree._ElementTree = etree.ElementTree(etree.fromstring(xml_str))
        root: etree._Element = tree.getroot()
        setupEle: etree._Element = root.find('setup')
        teardownEle: etree._Element = root.find('teardown')
        childrenFeaturesEle: etree._Element = root.find('childrenFeatures')
        caseLayerListEle: etree._Element = root.find('caseLayerList')
        if self.setup:
            setupEle.clear()
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionDetails)).getroot())
        if self.teardown:
            teardownEle.clear()
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionDetails)).getroot())
        childrenFeaturesEle.clear()
        for featureLayer in self.childrenFeatures:
            childrenFeaturesEle.append(etree.ElementTree(etree.fromstring(featureLayer.descriptionDetails)).getroot())
        caseLayerListEle.clear()
        for caseLayer in self.caseLayerList:
            case_tree = etree.ElementTree(etree.fromstring(caseLayer.descriptionDetails))
            case_root: etree._Element = case_tree.getroot()
            case_root.set('caseNum', caseLayer.caseNum)
            caseLayerListEle.append(case_root)

        new_xml = minidom.parseString(etree.tostring(tree.getroot()).replace(b'\n',b'').replace(b'\t',b'')).toprettyxml()
        new_xml: str = new_xml.replace('<?xml version="1.0" ?>', '')
        return new_xml

    @property
    def descriptionFull(self):
        """完整自我描述"""
        root = etree.Element('FeatureLayer')  # 根节点
        etree.SubElement(root, 'id', attrib={'value': str(id(self))})
        etree.SubElement(root, 'featureName', attrib={'value': str(self.featureName)})
        parentFeatureEle = etree.SubElement(root, 'parentFeatureLayer')
        etree.SubElement(root, 'childrenFeatures', attrib={'count': str(len(self.childrenFeatures))})
        setupEle = etree.SubElement(root, 'setup')
        teardownEle = etree.SubElement(root, 'teardown')
        caseLayerListEle = etree.SubElement(root, 'caseLayerList', attrib={'count': str(len(self.caseLayerList))})

        if self.parentFeatureLayer:
            parentFeatureEle.append(etree.ElementTree(etree.fromstring(self.parentFeatureLayer.descriptionSimple)).getroot())
        if self.setup:
            setupEle.append(etree.ElementTree(etree.fromstring(self.setup.descriptionSimple)).getroot())
        if self.teardown:
            teardownEle.append(etree.ElementTree(etree.fromstring(self.teardown.descriptionSimple)).getroot())
        for caseLayer in self.caseLayerList:
            caseLayerListEle.append(etree.ElementTree(etree.fromstring(caseLayer.descriptionSimple)).getroot())

        tree = etree.ElementTree(root)
        xml_str = minidom.parseString(etree.tostring(tree.getroot())).toprettyxml()
        xml_str: str = xml_str.replace('<?xml version="1.0" ?>', '')
        return xml_str

    @property
    def descriptionSimple(self):
        """简单自我描述"""
        return f'<FeatureLayer id="{id(self)}" featureName="{self.featureName}" caseCount="{len(self.caseLayerList)}"/>'

    @property
    def projectLayer(self): return self.__projectLayer
    @property
    def featureName(self): return self.__feature_name  # 功能分类名(目录名)
    @property
    def dirName(self): return self.__feature_name  # 目录名(功能分类名)
    @property
    def parentFeatureLayer(self) -> Optional[FeatureLayer]: return self.__parent  # 父级功能分类对象
    @property
    def childrenFeatures(self): return self.__children  # 子级功能分类对象
    @property
    def caseLayerList(self): return self.__caseLayerList  # 所有用例层级对象
    @property
    def setup(self): return self.__setup  # setup用例函数层级
    @property
    def teardown(self): return self.__teardown  # teardown用例函数层级
    @property
    def toLog(self): return self.projectLayer.toLog  # 日志对象
    @property
    def dtLog(self): return self.projectLayer.dtLog  # 日志对象
    @property
    def arguments(self): return self.projectLayer.arguments  # 本次运行参数

    def addChild(self, *childFeature):
        """添加子功能分类"""
        if not all(map(lambda c: isinstance(c, FeatureLayer), childFeature)):
            self.toLog.error(f'子级功能分类只能是 FeatureLayer！输入值：{childFeature}')
            raise TypeError('子级功能分类只能是 FeatureLayer！')
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
            if oneCaseFunc not in [cb.caseFunc for cb in self.caseLayerList]:
                self.__caseLayerList += (CaseLayer(oneCaseFunc, featureLayer=self, dirName=dirName),)

    def addCaseLayer(self, *caseLayer: CaseLayer):
        """储存用例对象"""
        if not all(map(lambda c: isinstance(c, CaseLayer), caseLayer)):
            self.toLog.error(f'本函数只能添加 CaseLayer！输入值：{caseLayer}')
            raise TypeError('本函数只能添加 CaseLayer！')
        if not all(map(lambda c: c.featureLayer is None or c.featureLayer is self, caseLayer)):
            self.toLog.error(f'只能添加本功能分类下的 CaseLayer！')
            raise TypeError('只能添加本功能分类下的 CaseLayer！')
        for _cLayer in caseLayer:
            if _cLayer.featureLayer is None:
                _cLayer.featureLayer = self
            if _cLayer not in self.caseLayerList and _cLayer.flag not in ('setup', 'teardown'):
                self.__caseLayerList += (_cLayer,)

    def getCaseLayer(self, caseNum: str):
        """获取1个用例层对象"""
        for caseLayer in self.caseLayerList:
            if caseLayer.caseNum == caseNum:
                return caseLayer
        return None

    def setSetupCaseLayer(self, setupCaseLayer: CaseLayer):
        """设置setup用例层对象"""
        if not isinstance(setupCaseLayer, CaseLayer):
            self.toLog.error(f'本函数只能添加 CaseLayer！输入值：{setupCaseLayer}')
            raise TypeError('本函数只能添加 CaseLayer！')
        setupCaseLayer.flag = 'setup'
        setupCaseLayer.featureLayer = self
        setupCaseLayer.dirName = self.dirName
        self.__setup = setupCaseLayer

    def setSetupFunc(self, setupFunc, module):
        """设置setup用例函数

        :type setupFunc: function
        :type module: ModuleType
        """
        self.__setup = CaseLayer(setupFunc, module, featureLayer=self, flag='setup', dirName=self.dirName)

    def setTeardownCaseLayer(self, teardownCaseLayer: CaseLayer):
        """设置teardown用例层对象"""
        if not isinstance(teardownCaseLayer, CaseLayer):
            self.toLog.error(f'本函数只能添加 CaseLayer！输入值：{teardownCaseLayer}')
            raise TypeError('本函数只能添加 CaseLayer！')
        teardownCaseLayer.flag = 'teardown'
        teardownCaseLayer.featureLayer = self
        teardownCaseLayer.dirName = self.dirName
        self.__teardown = teardownCaseLayer

    def setTeardownFunc(self, teardownFunc, module):
        """设置teardown用例函数

        :type teardownFunc: function
        :type module: ModuleType
        """
        self.__teardown = CaseLayer(teardownFunc, module, featureLayer=self, flag='teardown', dirName=self.dirName)

    def getRunningCaseLayer(self) -> List[CaseLayer]:
        """获取当前功能分类正在执行的用例，无则返回空"""
        runningCases = []
        if self.setup is not None and self.setup.running == RunningStatus.Running:
            runningCases.append(self.setup)
        if self.teardown is not None and self.teardown.running == RunningStatus.Running:
            runningCases.append(self.teardown)
        for caseLayer in self.caseLayerList:
            if caseLayer.running == RunningStatus.Running:
                runningCases.append(caseLayer)
        for childModule in self.childrenFeatures:
            runningCases += childModule.getRunningCaseLayer()
        return runningCases

    def getWillRunCaseLayers(self) -> List[CaseLayer]:
        """获取此功能分类下应该执行的所有用例"""
        willRunCases = []
        for caseLayer in self.caseLayerList:
            if caseLayer.shouldRun():
                willRunCases.append(caseLayer)
        for childModule in self.childrenFeatures:
            willRunCases += childModule.getWillRunCaseLayers()
        return willRunCases

    def shouldRun(self, feature: str = None):
        """根据feature判断本功能分类是否执行"""
        return not feature or feature == self.featureName

    def countRunCase(self) -> int:
        """统计本功能分类有多少需执行的用例"""
        count = 0
        if self.projectLayer.runBy == Enums.RunBy_arguments:
            feature = self.arguments.get('feature')
            tag = self.arguments['tag']
            untag = self.arguments.get('untag', '')
            if not self.shouldRun(feature):
                return 0
            count += sum([c.shouldRun(tag, untag) for c in self.caseLayerList])
        elif self.projectLayer.runBy == Enums.RunBy_skip:
            count += sum([not c.skip for c in self.caseLayerList])
        for childFeature in self.childrenFeatures:
            count += childFeature.countRunCase()
        return count

    def sortCaseLayerList(self):
        """将 CaseLayerList 按执行顺序排序"""
        caseLayerList = list(self.caseLayerList)
        caseLayerList.sort(key=lambda b: b.caseNum)
        caseLayerList.sort(key=lambda b: b.order)
        self.__caseLayerList = tuple(caseLayerList)

    def run(self):
        """执行该功能分类的用例

        :return: 成功数、失败数
        """
        ok = no = 0
        case_run_count = self.countRunCase()
        if case_run_count == 0:
            return ok, no

        if self.setup is not None:
            self.dtLog.info('')
            self.dtLog.info(f' {self.featureName} Setup Start '.center(75, '-'))
            if not self.setup.run():
                return ok, no

        self.dtLog.info('')
        self.dtLog.info(' Test Start '.center(75, '-'))
        self.dtLog.info(f' start execute module: {self.featureName} '.center(75, '-'))
        self.sortCaseLayerList()
        for caseLayer in self.caseLayerList:
            isPass = caseLayer.run()
            if isPass is None:
                continue
            elif isPass:
                ok += 1
            else:
                no += 1
        for childFeatureLayer in self.childrenFeatures:
            _ok, _no = childFeatureLayer.run()
            ok += _ok
            no += _no
        if self.teardown is not None:
            self.dtLog.info('')
            self.dtLog.info(f' {self.featureName} Teardown Start '.center(75, '-'))
            self.teardown.run()
        return ok, no

from .ProjectLayer import ProjectLayer
from .CaseLayer import CaseLayer