8.8 装了orm
todo：尝试移chara库 尝试新建guild库

目标：
建立guild库
 数据方面：
 1.任务库 带类别 奖励 等 
 2.小队库 和 characters表有外键链接
 3.任务状态：open → accepted → finished
                  → canceled → failed

部署方面：
1.单个小队成员能登陆 看见所有open 自己accepted任务
2.队长能够接受任务
3.admin能登录 负责新建任务

#leader bind party class