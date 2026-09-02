import models

#证明固定八级和顺序映射没有散架 证明它们符合真正的业务顺序
def test_adventurer_rank_order_matches_business_order():
    expected_rank_order = [
        models.AdventurerRank.COPPER,
        models.AdventurerRank.IRON,
        models.AdventurerRank.SILVER,
        models.AdventurerRank.GOLD,
        models.AdventurerRank.PLATINUM,
        models.AdventurerRank.MITHRIL,
        models.AdventurerRank.ORICHALCUM,
        models.AdventurerRank.ADAMANTITE,
    ]

    assert list(models.AdventurerRank) == expected_rank_order

    assert [
        models.ADVENTURER_RANK_ORDER[rank]
        for rank in expected_rank_order
    ] == list(range(len(expected_rank_order)))