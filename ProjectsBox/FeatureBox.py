# -*- coding: utf-8 -*-
# 创建时间:2025/7/1 23:01
# 创建人:天霄
# 基于 Python 3.11
# ========================================
# 业务功能分类盒子
# ========================================
from __future__ import annotations

from types import ModuleType
from typing import List, Tuple, Union, Optional, Callable, Dict, Any
from xml.dom import minidom
from lxml import etree

from .BaseType import *

class FeatureBox:
    """一个业务功能分类盒对象(目录)，储存该业务功能分类下的所有用例函数对象，也可储存父级、子级功能分类对象"""

    def __init__(self, name: str, projectBox, *, parentFeatureBox=None, caseBoxList=None):
        """功能分类盒子，包括父/子功功能分类盒子、用例盒子列表

        * 执行前将会对用例进行重新排序再执行：按次序号升序、用例编号升序
        * 由于次序号默认都是 ``1``，所以默认情况下将按用例编号升序执行

        :param str name: 功能分类名
        :param ProjectBox projectBox: 根项目盒子
        :param FeatureBox parentFeatureBox: 父级功能分类盒子，默认空
        :param List[CaseBox] caseBoxList: 所有下级用例盒子，默认空
        """
        if parentFeatureBox is not None and not isinstance(parentFeatureBox, FeatureBox):
            self.toLog.error(f'父级只能是 FeatureBox！输入值：{parentFeatureBox}')
            raise TypeError('父级只能是 FeatureBox！')
        self.__feature_name: str = name
        self.__parent: FeatureBox = parentFeatureBox
        self.__children: Tuple[FeatureBox, ...] = ()
        self.__caseBoxList: Tuple[CaseBox, ...] = caseBoxList and tuple(caseBoxList) or ()
        self.__setup: CaseBox | None = None
        self.__teardown: CaseBox | None = None
        self.__projectBox = projectBox
        if self not in projectBox.featureBoxes:
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
    def parentFeatureBox(self) -> Optional[FeatureBox]: return self.__parent  # 父级功能分类对象
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
    def dtLog(self): return self.projectBox.dtLog  # 日志对象
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
            self.dtLog.info('')
            self.dtLog.info(f' {self.featureName} Setup Start '.center(75, '-'))
            if not self.setup.run():
                return ok, no

        self.dtLog.info('')
        self.dtLog.info(' Test Start '.center(75, '-'))
        self.dtLog.info(f' start execute module: {self.featureName} '.center(75, '-'))
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
            self.dtLog.info('')
            self.dtLog.info(f' {self.featureName} Teardown Start '.center(75, '-'))
            self.teardown.run()
        return ok, no

from .ProjectBox import ProjectBox
from .CaseBox import CaseBox