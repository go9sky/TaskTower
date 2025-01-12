# -*- coding: utf-8 -*-
# 创建日期：2024/5/21
# 作者：天霄
# 简介：
import pathlib
import re
import traceback


class WithLogTag:
    def __init__(self, **kwargs):
        """特殊日志标签的上下文管理器，在开头结尾打印指定tag和信息

        :param enterTag: 进入时前置tag
        :param exitTag: 退出时前置tag
        :param enterMsg: 进入时打印的日志
        :param exitMsg: 退出时打印的日志，默认无，中途可变
        :param logger: 日志对象，默认全部使用print
        :param tb_callback: 当发生错误时的错误调用栈回调函数，接收一个错误信息字符串参数。默认无
        :param raiseError: 退出时捕获错误是否抛出，默认是

        使用示例::

            with WithLogTag(
                    enterTag="## Request  ##",
                    exitTag="## Response ##",
                    enterMsg="msg1",
                    exitMsg="msg2") as w:
                w.exitMsg = "msg3"

        输出::

            > “## Request  ## msg1”
            > “## Response ## msg3”
        """
        self._enterTag = kwargs.get("enterTag", '')
        self._enterMsg = kwargs.get("enterMsg", '')
        self._exitTag = kwargs.get("exitTag", '')
        self._logger = kwargs.get("logger", type('_Logger', (), {'info': print, 'error': print})())
        self._raiseError = kwargs.get("raiseError", True)
        self.exitMsg = kwargs.get("exitMsg", "")  # 无异常时，允许手动添加附加信息
        self.isSuccess = True  # 无异常时，允许手动标记成功或失败
        self.tb_callback = kwargs.get('tb_callback') or (lambda tb: None)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f'<WithLogTag enterTag="{self._enterTag}" exitTag="{self._exitTag}">'

    def __enter__(self):
        """进入时打印"""
        self._logger.info(f"{self._enterTag} {self._enterMsg}".strip())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时有异常则记录error，无异常则记录info，及退出信息

        :param exc_type: 错误类型
        :param exc_val: 错误信息
        :param exc_tb: 调用栈
        :return:
        """
        # 存在异常，记录error及异常信息、详细调用栈
        if exc_type is not None:
            if issubclass(exc_type, Exception):
                tb = f'{exc_type.__name__}: {exc_val}\nAt: \n{traceback.format_exc().replace(str(pathlib.Path.cwd()), "")}'  # 含关联错误的堆栈
                # tb = f'{exc_type.__name__}: {exc_val}\nAt: \n{"".join(traceback.format_tb(exc_tb)).replace(str(pathlib.Path.cwd()), "")}'  # 仅该错误的堆栈
                self._logger.error(f"{self._exitTag} {tb}")
                self.tb_callback(tb)
                return not self._raiseError
            elif issubclass(exc_tb, BaseException):
                tb = f'{exc_type.__name__}{str(exc_val) and f": {exc_val}" or ""}'
                self._logger.error(f"{self._exitTag} {tb}")
                self.tb_callback(tb)
                return False
        record = self._logger.info
        if not self.isSuccess:  # 无异常，标记失败则使用error记录
            record = self._logger.error
        record(f"{self._exitTag} {self.exitMsg}".strip())


class WithStep(WithLogTag):
    def __init__(self, step, **kwargs):
        """step上下文管理器，在开头记录step，末尾记录step成功/失败

        :param step: step字符串
        :param logger: 日志对象，默认全部使用print
        :param tb_callback: 当发生错误时的错误调用栈回调函数，接收一个错误信息字符串参数。默认无
        :param raiseError: 退出时捕获错误是否抛出，默认是

        使用示例::

            with WithStep("step1: 连接电表"):
                pass

        输出::

            > “step1: 连接电表”
            > “step1: 连接电表 *Succeeded!*”
        """
        super().__init__(enterTag="", exitTag="", enterMsg=step, **kwargs)
        self.step = self._enterMsg

    def __str__(self):
        return f"<WithStep={self.step!r}>"

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时有异常则记录失败，无异常且不跳过则记录成功

        :param exc_type: 错误类型
        :param exc_val: 错误信息
        :param exc_tb: 调用栈
        :return:
        """
        # 存在异常，直接失败，记录异常信息、详细调用栈
        if exc_type is not None:
            if issubclass(exc_type, Exception):
                self._logger.error(f"{self.step} *Failed!* {exc_val}")
                tb = f'{exc_type.__name__}  At: \n{traceback.format_exc().replace(str(pathlib.Path.cwd()), "")}'  # 含关联错误的堆栈
                # tb = f'{exc_type.__name__}  At: \n{"".join(traceback.format_tb(exc_tb)).replace(str(pathlib.Path.cwd()), "")}'  # 仅该错误的堆栈
                self._logger.error(tb)
                self.tb_callback(tb)
                return not self._raiseError
            elif issubclass(exc_type, BaseException):
                tb = f'{exc_type.__name__}{str(exc_val) and f": {exc_val}" or ""}'
                self._logger.error(f"{self.step} *Failed!* {tb}")
                self.tb_callback(tb)
                return False
        if not self.isSuccess:  # 无异常，标记失败则失败
            self._logger.error(f"{self.step} *Failed!* {self.exitMsg}")
        elif self.isSuccess:
            self._logger.info(f"{self.step} *Succeeded!* {self.exitMsg}")


class Step:
    """定义步骤字符串对象，多个步骤无关联"""
    def __init__(self, description: str, index=1, childIndex=None, parseFromMsg=False, prefix='step'):
        """定义步骤字符串对象

        :param description: 步骤描述信息
        :param index: 步骤索引，不传则默认生成索引1
        :param childIndex: 子步骤索引，默认空
        :param parseFromMsg: 根据步骤描述解析出三部分，默认否（若是，则忽略传入索引，由字符信息解析索引）
        :param prefix: 前缀，默认step
        """
        description = description.strip()
        self._logger = None
        self._tb_callback = None
        if not parseFromMsg:
            self.index = index
            self.description = description
            self.childIndex = childIndex
            self.prefix = prefix or 'step'
        else:
            match = re.match(r'^(\w*step)(\d+)[-|.]*(\d*)\s*:\s*(.*?)$', description, re.I)
            if not match:
                raise ValueError(f'无法解析步骤索引：{description}')
            self.prefix = match.group(1)
            self.index = int(match.group(2))
            self.childIndex = None if not match.group(3) else int(match.group(3))
            self.description = match.group(4)

    @property
    def logger(self): return self._logger

    @logger.setter
    def logger(self, logger):
        """设置withStep时的默认日志对象"""
        if hasattr(logger, 'info') and hasattr(logger, 'error'):
            self._logger = logger
        else:
            raise TypeError('logger 必须含有 info 和 error 方法！')

    @property
    def stepName(self):
        """步骤名，如：step1、step3-2"""
        if self.childIndex is None:
            return f'{self.prefix}{self.index}'
        return f'{self.prefix}{self.index}-{self.childIndex}'

    def __repr__(self):
        return f"Step(description='{str(self)}', parseFromMsg=True)"

    def __str__(self):
        return f'{self.stepName}: {self.description}'

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        """比较是否相等"""
        if isinstance(other, (Step, str)):
            return str(self) == str(other)
        return False

    def __ne__(self, other):
        """比较是否不等"""
        return not self.__eq__(other)

    def getChildIndex(self) -> int:
        """获取子步骤索引，空则返回1

        示例：
            - step5 --> 1
            - step6-2 --> 2

        :return:
        """
        if self.childIndex is None:
            return 1
        return self.childIndex

    def nextIndex(self) -> int:
        """下一步的索引"""
        return self.index + 1

    def nextChildIndex(self) -> int:
        """本步骤的下一子步骤索引，若没有子步骤则为1

        示例：
            - step5 --> 1
            - step6-2 --> 3
        :return:
        """
        if self.childIndex is None:
            return 1
        return self.childIndex + 1

    def convertStep(self, description, prefix=None):
        """序号不变，仅变换信息后生成一个步骤"""
        return Step(description, self.index, self.childIndex, prefix=prefix or self.prefix)

    def bornChildStep(self, description, prefix=None):
        """生出一个子步骤，本身就是子步骤则序号不变，本身非子步骤则子步骤序号为1

        示例：
            - step5... --> step5-1...
            - step6-2... --> step6-2...

        :param description: 步骤描述
        :param prefix: 指定前缀，默认当前前缀
        :return: 新的Step对象
        """
        return Step(description, self.index, self.getChildIndex(), prefix=prefix or self.prefix)

    def nextStep(self, description, prefix=None):
        """生成下一步骤，无子步骤"""
        return Step(description, self.nextIndex(), prefix=prefix or self.prefix)

    def nextChildStep(self, description, prefix=None):
        """生成下一个子步骤，若没有子步骤则子步骤序号为1

        示例：
            - step5... --> step5-1...
            - step6-2... --> step6-3...

        :param description: 步骤描述
        :param prefix: 指定前缀，默认为step
        :return: 新的Step对象
        """
        return Step(description, self.index, self.nextChildIndex(), prefix=prefix or self.prefix)

    def withStep(self, logger=None) -> WithStep:
        """生成一个step的上下文管理器，记录函数默认为 print

        - 日志管理器函数：
          - 若传入函数对象，则以传入为准
          - 若不传入：
            - 若已设置日志对象，则取该日志对象
            - 若未设置日志对象，则为默认None（print）

        :param logger: 日志记录对象
        :return: WithStep()
        """
        try:
            self.logger = logger
        except TypeError:
            ...
        return WithStep(str(self), logger=self.logger, tb_callback=self._tb_callback)


