using UnrealBuildTool;

public class UCADeveloperTools : ModuleRules
{
    public UCADeveloperTools(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new[]
            {
                "Core"
            }
        );

        PrivateDependencyModuleNames.AddRange(
            new[]
            {
                "CoreUObject",
                "DesktopPlatform",
                "EditorFramework",
                "Engine",
                "InputCore",
                "LevelEditor",
                "Projects",
                "Slate",
                "SlateCore",
                "ToolMenus",
                "UnrealEd"
            }
        );
    }
}
