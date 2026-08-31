

# 数据：
 
 1.任务库 带类别 奖励 等 
 2.小队库 和 characters表有外键链接


## 身份管理
野人character---（user register）--→user---（add member）--→party_member

## quest：

发布（admin）
接取（party_leader）
提交（party_leader）?未做
审核结果(admin)？
任务状态：open → recuiting? commenced → (submitted)?
    finished → canceled → failed

后端


# todo
- [] 外围政策：
        用户名长度
        一次能接多少任务
        接受任务等级限制
        任务完成度 评分
        政策补贴性任务
        用户等级提升机制

- [x]招聘模块 add member不就是吗

- []用户查看自己小队和自己的任务。分：
        正执行的（recuiting commenced）
        已完成的（finished）
        失败的（withdraw failed 都写failed吧）
- []合作任务recuiting状态增加 为了给 pariticipation表过滤目前正执行的

- []提交和奖励模块
- []"detail"本地化