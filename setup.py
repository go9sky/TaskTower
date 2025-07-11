# -*- coding: utf-8 -*-
# 创建日期：2024/11/19
# 作者：天霄
# 简介：打包初始化信息
from pathlib import Path
from setuptools import find_packages, setup
from TaskTower import __version__

require_list = Path("requirements.txt").read_text('utf-8').splitlines()
long_description = Path("ReadMe.md").read_text('utf-8')

setup(
    name="TaskTower",  # 应用名
    version=__version__,  # 版本号
    url='https://gitee.com/go9sky/TaskTower.git',
    author='go9sky',
    author_email='toptobest@163.com',
    description='TaskTower （任务塔）一个任务执行与状态监控装载器',  # 简要描述
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='MIT',
    packages=find_packages(),  # 包括在安装包内的 Python 包
    install_requires=require_list,
    python_requires='>=3.6'
)
