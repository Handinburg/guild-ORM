#这又是 pytest 的约定魔法。
#conftest.py
# → pytest认的特殊文件名
# → pytest运行时自动寻找并加载fixture

#每个测试开始前：
# 删除测试数据库里的所有表，清掉上个测试留下的东西。
import pytest

import models
from tests.helpers import test_engine


@pytest.fixture(autouse=True)
def reset_test_database():
    
    models.Base.metadata.drop_all(bind=test_engine)
    models.Base.metadata.create_all(bind=test_engine)

    yield

    models.Base.metadata.drop_all(bind=test_engine)
