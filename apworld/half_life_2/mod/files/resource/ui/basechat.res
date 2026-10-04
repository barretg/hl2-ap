// Chat panel layout. Half-Life 2 ships none (its retail client never opens
// chat in single player), so without this the input line and history have no
// size and chat opens invisibly. Positions are relative to the HudChat panel
// placed by scripts/hudlayout.res.
"Resource/UI/BaseChat.res"
{
	"HudChat"
	{
		"ControlName"		"EditablePanel"
		"fieldName"		"HudChat"
		"visible"		"1"
		"enabled"		"1"
		"xpos"			"10"
		"ypos"			"275"
		"wide"			"320"
		"tall"			"120"
		"PaintBackgroundType"	"2"
	}
	"ChatInputLine"
	{
		"ControlName"		"EditablePanel"
		"fieldName"		"ChatInputLine"
		"visible"		"1"
		"enabled"		"1"
		"xpos"			"10"
		"ypos"			"100"
		"wide"			"300"
		"tall"			"14"
		"PaintBackgroundType"	"0"
	}
	"ChatFiltersButton"
	{
		"ControlName"		"Button"
		"fieldName"		"ChatFiltersButton"
		"visible"		"0"
		"enabled"		"0"
		"xpos"			"285"
		"ypos"			"2"
		"wide"			"30"
		"tall"			"10"
		"labelText"		""
	}
	"HudChatHistory"
	{
		"ControlName"		"RichText"
		"fieldName"		"HudChatHistory"
		"visible"		"1"
		"enabled"		"1"
		"xpos"			"10"
		"ypos"			"10"
		"wide"			"300"
		"tall"			"86"
		"wrap"			"1"
		"autoResize"		"1"
		"pinCorner"		"1"
		"labelText"		""
		"textAlignment"		"south-west"
		"font"			"ChatFont"
		"maxchars"		"-1"
	}
}
