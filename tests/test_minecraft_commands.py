"""她的目標要編成 Mindcraft 指令，身體才不會亂猜。"""

from src.open_llm_vtuber.minecraft.commands import compile_goal


def test_wood_in_many_spellings():
    assert compile_goal("collect 10 oak logs") == ['!collectBlocks("oak_log", 10)']
    assert compile_goal("gather wood") == ['!collectBlocks("oak_log", 10)']
    assert compile_goal("chop a tree") == ['!collectBlocks("oak_log", 10)']
    assert compile_goal("punch tree") == ['!collectBlocks("oak_log", 10)']


def test_survival_chain():
    assert (
        compile_goal("craft a crafting table")[-1]
        == '!craftRecipe("crafting_table", 1)'
    )
    assert compile_goal("craft a wooden pickaxe") == [
        '!craftRecipe("oak_planks", 2)',
        '!craftRecipe("stick", 1)',
        '!craftRecipe("wooden_pickaxe", 1)',
    ]
    assert compile_goal("collect 8 cobblestone") == ['!collectBlocks("stone", 8)']
    assert (
        compile_goal("craft a stone pickaxe")[-1] == '!craftRecipe("stone_pickaxe", 1)'
    )
    assert compile_goal("collect 5 coal") == ['!collectBlocks("coal_ore", 5)']
    assert compile_goal("craft 8 torches") == ['!craftRecipe("torch", 2)']
    assert compile_goal("kill a cow and collect the beef") == ['!attack("cow")']
    assert compile_goal("dig into the hillside and make a small shelter") == [
        "!digDown(3)"
    ]
    assert compile_goal("mine 5 raw iron underground") == [
        '!collectBlocks("iron_ore", 5)'
    ]


def test_unknown_goal_is_dropped():
    assert compile_goal("follow the river east") == []
    assert compile_goal("look around") == []


def test_player_requests():
    assert compile_goal("follow me") == ['!followPlayer("Player", 3)']
    assert compile_goal("come here") == ['!goToPlayer("Player", 3)']
    assert compile_goal("stop") == ["!stop"]
