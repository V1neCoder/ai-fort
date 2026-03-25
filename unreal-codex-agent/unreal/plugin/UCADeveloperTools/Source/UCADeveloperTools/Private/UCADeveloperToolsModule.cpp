#include "UCADeveloperToolsModule.h"

#include "LevelEditor.h"
#include "SUCADeveloperToolsPanel.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"

#define LOCTEXT_NAMESPACE "FUCADeveloperToolsModule"

static const FName UCADeveloperToolsTabName(TEXT("UCADeveloperTools"));

void FUCADeveloperToolsModule::StartupModule()
{
    FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
        UCADeveloperToolsTabName,
        FOnSpawnTab::CreateRaw(this, &FUCADeveloperToolsModule::OnSpawnPluginTab)
    )
    .SetDisplayName(LOCTEXT("UCADeveloperToolsTabTitle", "UCA Developer Tools"))
    .SetMenuType(ETabSpawnerMenuType::Hidden);

    UToolMenus::RegisterStartupCallback(
        FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FUCADeveloperToolsModule::RegisterMenus)
    );
}

void FUCADeveloperToolsModule::ShutdownModule()
{
    UToolMenus::UnRegisterStartupCallback(this);
    UToolMenus::UnregisterOwner(this);
    FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(UCADeveloperToolsTabName);
}

TSharedRef<SDockTab> FUCADeveloperToolsModule::OnSpawnPluginTab(const FSpawnTabArgs& SpawnTabArgs)
{
    return SNew(SDockTab)
        .TabRole(ETabRole::NomadTab)
        [
            SNew(SUCADeveloperToolsPanel)
        ];
}

void FUCADeveloperToolsModule::PluginButtonClicked()
{
    FGlobalTabmanager::Get()->TryInvokeTab(UCADeveloperToolsTabName);
}

void FUCADeveloperToolsModule::RegisterMenus()
{
    FToolMenuOwnerScoped OwnerScoped(this);

    UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Window");
    FToolMenuSection& Section = Menu->FindOrAddSection("WindowLayout");
    Section.AddMenuEntry(
        "UCADeveloperTools",
        LOCTEXT("UCADeveloperToolsMenuLabel", "UCA Developer Tools"),
        LOCTEXT("UCADeveloperToolsMenuToolTip", "Open the unreal-codex-agent developer tools panel."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateRaw(this, &FUCADeveloperToolsModule::PluginButtonClicked))
    );
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FUCADeveloperToolsModule, UCADeveloperTools)
