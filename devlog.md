

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
任务状态：recuiting? commenced → (submitted)?
    finished → canceled → failed

         正在招募、正在执行、暂缓
        → 可以退出，只删除Participation

        已经完成、取消、失败
        → 不允许退出，保留Participation用于closed查询


# todo

- ## [x] policies一期:外挂 尽量解耦便于调整

- [x] user regis政策
- [x] participate政策
- [x] party 政策
- [x] quest policy - []政策补贴性任务 归为二期

- ## [x] ranking一期：不挂在政策上 是底层逻辑:

- [x]用户default rank      
- [x]管理员uprank user接口
- [x]小队rank：设计成队伍里最高等级即可 
                小队等级不要存进 Party 表。
- [x]需要外挂政策的：是否允许跨级组队
        policy:max_rank_gap = 1
        policy_excecutor:
                left:exisiting_ranks=get_list_of_existing_ranks

                e.g:exisiting_ranks=[gold,silver]:
                        allowed_next_member_rank in [gold,silver]
                if exisiting_ranks=[gold]: 
                        allowed_next_member_rank in [gold,silver,platinum]

                what if gap = 2?
                if e_r = [gold,silver]:
                        a_r = [gold,silver,copper,platinum]

                solve:
                        def(check_rank_policy):
                        new_ranks = existing_ranks.append(party_member_data.user_rank)

                        now_gap = max(i for i in new_ranks)-min。。。
                        if now_gap> policy.max_rank_gap:
                                raise http...
                        return party_member_data
        routers:add_party_member(
                party_member_data:schemas.PartyMemberCreate = 
                depends(check add member policy))

- [x]管理员创建任务 指定minimum_rank
        quest_create
- [x]队长接任务 加入底层判定 你队伍够不够格
        routers participation
                def accept quest(... quest_id:int)
                left: get existing party rank:
                        now_ranks_position = [
                                models.ADVENTURER_RANK_ORDER[
                                models.AdventurerRank(
                                member.user.adventurer_rank
                                )
                        ]
                        for member in party.member_list
                right: minimum_rank = db.scalar(quest.minimum_rank where quest.id = quest_id)
                if max (now.. ) < minimum_rank:
                        raise...

##  -[]用户查看自己小队和自己的任务。分：
        正执行的（recuiting commenced）
        已完成的（finished）
        失败的（withdraw failed 都写failed吧）

- [x] get my party 暂时不做履历
- [] get my quest all(status = * 包括withdraw failed finished open commenced）
        只设置 正常：recruiting→commenced→finished  
                异常：canceled、posponed、failed、
        多个小队 本来就可以接一个任务 只要任务是 open→accepted（或recruiting？）状态 
        真的打算一个队做的任务 就直接要求前台commenced
        去掉 is_cooperative 字段 
        管理员手动commence后 就不在开放接取

        管理员的修改 可以跳 不设顺序限制
- [] v2：历史记录 包含withdrawn动作留痕
- [] v2: 加admin审核accept quest接口
- [] v2: admin create_quest 暂存功能



- [x]任务完成度 评分 不做了 管理员手动
- [x]招聘模块 add member不就是吗

## -[]detail"本地化