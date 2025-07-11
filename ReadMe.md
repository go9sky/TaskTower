# TaskTower

## 简介
一个测试用例项目加载工具。将每个项目抽象分为项目（`ProjectLayer`）、模块分类（`FeatureLayer`）、用例函数（`CaseLayer`）、步骤（`StepLayer`）四个层级，
形成一个树形结构，通过`ProjectLayer.run()`执行整个测试用例项目。

**注意**：本库初衷是为了能实时查看用例执行状态，并且尽可能不侵入原脚本，所以将自动化测试的层级抽象类化装载，而并非要求重写脚本。

- 适用于长时间执行的自动化用例项目，可提供实时状态查询。
- 也可用于长时间运行的任务监控。

**最低侵入性使用要求**：用例函数在执行通过时必须返回`0`（默认0，可修改代表这个成功的返回值），其他无返回、任何返回、任何异常都视为用例失败。


## 安装

1. 打包为 `.whl` 文件
    ```
    pip install wheel setuptools
    python setup.py bdist_wheel
    ```

2. 通过 `.whl` 文件安装
    ```
    pip install dist/TaskTower-1.0-py3-none-any.whl
    ```


## 用法示例

```python
from pathlib import Path
from TaskTower import ProjectLayer, FeatureLayer, CaseLayer, BaseCase, baseConfig

baseConfig.successFlag = 0  # 设置用例执行成功标志，默认为0


projectLayer = ProjectLayer(Path('.'))  # 用例项目初始化，设置项目根目录
featureLayer = FeatureLayer('feature1', projectLayer)  # 模块分类初始化，设置模块分类名称、所属项目。这个名称可以是子目录名
# 以上两行代码的含义是：有一个当前目录的项目，项目下有个 feature1 模块分类


def beforeCase(func):
    """示例装饰器"""
    def wrapper(*args, **kwargs):
        projectLayer.dtLog.info('beforeCase'.center(60, '-'))
        return func(*args, **kwargs)
    return wrapper


# ############# 方式一：耦合性较低，定义执行函数即可，仅返回0代表成功 ###########
@beforeCase
def case_001():
    """TestCase: case_001, 测试用例001"""
    projectLayer.dtLog.info("开始测试步骤***1")
    projectLayer.dtLog.info("开始测试步骤***2")
    return 0


# ############# 方式二：耦合性非常高，继承BaseCase（也可自行重写此类）后，在init中定义用例属性和步骤属性，在run方法中串联步骤逻辑 ###########
class Case(BaseCase):
    # 用例基本属性
    case_num = 'case_001'
    case_title = '测试用例001'
    case_tag = ('abc',)

    def init(self):
        # 定义用例属性、步骤属性
        self.caseLayer = CaseLayer(self.run, featureLayer=featureLayer)
        self.step1 = self.addStepLayer("step1: 测试步骤1", lambda x: projectLayer.dtLog.info(f'开始测试步骤***{x}'))
        self.step2 = self.addStepLayer('step2: 测试步骤2', lambda x: projectLayer.dtLog.info(f'开始测试步骤***{x}'))

    @beforeCase
    def run(self):
        # 串联执行步骤
        self.step1.runStep(1)
        self.step2.runStep(2)
        return 0


if __name__ == '__main__':
    CaseLayer(case_001, featureLayer=featureLayer)  # ####### 取消注释后则是方式一
    # featureLayer.addCaseLayer(Case().caseLayer)  # ####### 取消注释后则是方式二

    projectLayer.dtLog.info('=' * 80)
    ok, no = projectLayer.run()
    projectLayer.dtLog.info('=' * 80)
    projectLayer.dtLog.info(f'通过用例数：{ok}，不通过用例数：{no}')
```

