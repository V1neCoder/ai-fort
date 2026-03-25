#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FUCADeveloperToolsModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    void RegisterMenus();
    void PluginButtonClicked();
    TSharedRef<class SDockTab> OnSpawnPluginTab(const class FSpawnTabArgs& SpawnTabArgs);
};
