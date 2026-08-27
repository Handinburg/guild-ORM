目标：
建立guild库
 数据方面：
 1.任务库 带类别 奖励 等 
 2.小队库 和 characters表有外键链接
 3.任务状态：open → commenced → (submitted)?
    finished → canceled → failed

业务流程：
1.身份管理
野人character---（sign in）--→user---（recruit）--→party_member

2.任务流程管理
发布（admin）
接取（party_leader）
提交（party_leader）?未做
审核结果(admin)

仍要做的路由：
1.招聘模块
2.提交模块
3.野人注册模块

部署方面：
什么jwt乱七八糟的


外围政策：用户名长度 
接受任务等级限制
任务完成度 评分
政策补贴任务
冒险者级别

"detail"本地化