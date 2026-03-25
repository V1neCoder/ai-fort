#pragma once

#include "CoreMinimal.h"
#include "Input/Reply.h"
#include "Widgets/SCompoundWidget.h"

class STextBlock;
class SVerticalBox;

class SUCADeveloperToolsPanel : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SUCADeveloperToolsPanel) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

private:
    FString ResolveRepoRoot() const;
    FString FindLatestXRayHtml() const;
    FString SessionsRoot() const;
    void SetStatus(const FString& Message) const;
    EVisibility GetToolListVisibility() const;

    FReply HandleOpenLatestXRay();
    FReply HandleOpenSessionsFolder();
    FReply HandleOpenProjectConfig();
    FReply HandleToggleToolList();

    bool bShowToolList = true;
    TSharedPtr<STextBlock> StatusText;
    TSharedPtr<SVerticalBox> ToolListBox;
};
