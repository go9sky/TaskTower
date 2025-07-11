# -*- coding: utf-8 -*-
# 创建日期：2024/11/19
# 作者：天霄
# 简介：打包初始化信息
from pathlib import Path
from setuptools import find_packages, setup

# 读取依赖
require_list = Path("requirements.txt").read_text('utf-8').splitlines()

setup(
    name="ExecuteTower",  # 应用名
    version='1.0',  # 版本号
    url='https://gitee.com/go9sky/ExecuteTower.git',
    packages=find_packages(),  # 包括在安装包内的 Python 包
    install_requires=require_list,
    python_requires='>=3.6'
)
