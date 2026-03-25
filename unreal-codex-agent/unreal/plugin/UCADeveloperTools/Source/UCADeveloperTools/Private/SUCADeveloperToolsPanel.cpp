#include "SUCADeveloperToolsPanel.h"

#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformMisc.h"
#include "Misc/Paths.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "SUCADeveloperToolsPanel"

namespace
{
    TArray<FString> ToolDescriptions()
    {
        return {
            TEXT("Scene Identification Scan: Show green for understood actors and red for undefined ones."),
            TEXT("Undefined Actor Triage: Surface missing tags, dimensions, quarantine state, and trust gaps."),
            TEXT("Per-Cycle X-Ray Reports: Open the latest HTML and JSON artifacts written by the orchestrator."),
            TEXT("Cleaner Review Mode: Hide the tool list when you want a panel that feels closer to a built-in editor utility."),
        };
    }
}

void SUCADeveloperToolsPanel::Construct(const FArguments& InArgs)
{
    ChildSlot
    [
        SNew(SBorder)
        .Padding(12.0f)
        [
            SNew(SScrollBox)
            + SScrollBox::Slot()
            [
                SNew(SVerticalBox)

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 8.0f)
                [
                    SNew(STextBlock)
                    .Text(LOCTEXT("Title", "UCA Developer Tools"))
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 12.0f)
                [
                    SNew(STextBlock)
                    .Text(LOCTEXT("Subtitle", "Built-in Unreal panel for the developer x-ray workflow."))
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 8.0f)
                [
                    SNew(SButton)
                    .Text(LOCTEXT("OpenLatestXRay", "Open Latest X-Ray"))
                    .OnClicked(this, &SUCADeveloperToolsPanel::HandleOpenLatestXRay)
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 8.0f)
                [
                    SNew(SButton)
                    .Text(LOCTEXT("OpenSessionsFolder", "Open Sessions Folder"))
                    .OnClicked(this, &SUCADeveloperToolsPanel::HandleOpenSessionsFolder)
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 8.0f)
                [
                    SNew(SButton)
                    .Text(LOCTEXT("OpenProjectConfig", "Open Project Config"))
                    .OnClicked(this, &SUCADeveloperToolsPanel::HandleOpenProjectConfig)
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 12.0f)
                [
                    SNew(SButton)
                    .Text(LOCTEXT("ToggleToolList", "Hide / Show Tool List"))
                    .OnClicked(this, &SUCADeveloperToolsPanel::HandleToggleToolList)
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 12.0f)
                [
                    SAssignNew(StatusText, STextBlock)
                    .Text(LOCTEXT("StatusReady", "Ready"))
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                .Padding(0.0f, 0.0f, 0.0f, 8.0f)
                [
                    SNew(SSeparator)
                ]

                + SVerticalBox::Slot()
                .AutoHeight()
                [
                    SAssignNew(ToolListBox, SVerticalBox)
                    .Visibility(this, &SUCADeveloperToolsPanel::GetToolListVisibility)
                ]
            ]
        ]
    ];

    for (const FString& Description : ToolDescriptions())
    {
        ToolListBox->AddSlot()
        .AutoHeight()
        .Padding(0.0f, 0.0f, 0.0f, 8.0f)
        [
            SNew(SBorder)
            .Padding(8.0f)
            [
                SNew(STextBlock)
                .Text(FText::FromString(Description))
                .AutoWrapText(true)
            ]
        ];
    }
}

FString SUCADeveloperToolsPanel::ResolveRepoRoot() const
{
    const FString EnvRepoRoot = FPlatformMisc::GetEnvironmentVariable(TEXT("UCA_REPO_ROOT"));
    if (!EnvRepoRoot.IsEmpty() && IFileManager::Get().DirectoryExists(*EnvRepoRoot))
    {
        return EnvRepoRoot;
    }

    FString Candidate = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
    for (int32 Depth = 0; Depth < 6; ++Depth)
    {
        const FString SessionsPath = FPaths::Combine(Candidate, TEXT("data"), TEXT("sessions"));
        if (IFileManager::Get().DirectoryExists(*SessionsPath))
        {
            return Candidate;
        }

        const FString Parent = FPaths::GetPath(Candidate);
        if (Parent.IsEmpty() || Parent == Candidate)
        {
            break;
        }
        Candidate = Parent;
    }

    return FString();
}

FString SUCADeveloperToolsPanel::SessionsRoot() const
{
    const FString RepoRoot = ResolveRepoRoot();
    if (RepoRoot.IsEmpty())
    {
        return FString();
    }
    return FPaths::Combine(RepoRoot, TEXT("data"), TEXT("sessions"));
}

FString SUCADeveloperToolsPanel::FindLatestXRayHtml() const
{
    const FString Root = SessionsRoot();
    if (Root.IsEmpty())
    {
        return FString();
    }

    TArray<FString> SessionDirectories;
    IFileManager::Get().FindFiles(SessionDirectories, *FPaths::Combine(Root, TEXT("*")), false, true);

    FDateTime LatestTime = FDateTime::MinValue();
    FString LatestFile;

    for (const FString& SessionDirectory : SessionDirectories)
    {
        const FString Candidate = FPaths::Combine(Root, SessionDirectory, TEXT("developer_xray"), TEXT("current.html"));
        if (!IFileManager::Get().FileExists(*Candidate))
        {
            continue;
        }

        const FDateTime Timestamp = IFileManager::Get().GetTimeStamp(*Candidate);
        if (Timestamp > LatestTime)
        {
            LatestTime = Timestamp;
            LatestFile = Candidate;
        }
    }

    return LatestFile;
}

void SUCADeveloperToolsPanel::SetStatus(const FString& Message) const
{
    if (StatusText.IsValid())
    {
        StatusText->SetText(FText::FromString(Message));
    }
}

EVisibility SUCADeveloperToolsPanel::GetToolListVisibility() const
{
    return bShowToolList ? EVisibility::Visible : EVisibility::Collapsed;
}

FReply SUCADeveloperToolsPanel::HandleOpenLatestXRay()
{
    const FString HtmlPath = FindLatestXRayHtml();
    if (HtmlPath.IsEmpty())
    {
        SetStatus(TEXT("No current x-ray HTML was found yet."));
        return FReply::Handled();
    }

    FPlatformProcess::LaunchFileInDefaultExternalApplication(*HtmlPath);
    SetStatus(FString::Printf(TEXT("Opened latest x-ray: %s"), *HtmlPath));
    return FReply::Handled();
}

FReply SUCADeveloperToolsPanel::HandleOpenSessionsFolder()
{
    const FString Root = SessionsRoot();
    if (Root.IsEmpty())
    {
        SetStatus(TEXT("Could not resolve the repo sessions folder."));
        return FReply::Handled();
    }

    FPlatformProcess::ExploreFolder(*Root);
    SetStatus(FString::Printf(TEXT("Opened sessions folder: %s"), *Root));
    return FReply::Handled();
}

FReply SUCADeveloperToolsPanel::HandleOpenProjectConfig()
{
    const FString RepoRoot = ResolveRepoRoot();
    if (RepoRoot.IsEmpty())
    {
        SetStatus(TEXT("Could not resolve the repo root."));
        return FReply::Handled();
    }

    const FString ConfigPath = FPaths::Combine(RepoRoot, TEXT("config"), TEXT("project.json"));
    if (!IFileManager::Get().FileExists(*ConfigPath))
    {
        SetStatus(TEXT("project.json was not found."));
        return FReply::Handled();
    }

    FPlatformProcess::LaunchFileInDefaultExternalApplication(*ConfigPath);
    SetStatus(FString::Printf(TEXT("Opened config: %s"), *ConfigPath));
    return FReply::Handled();
}

FReply SUCADeveloperToolsPanel::HandleToggleToolList()
{
    bShowToolList = !bShowToolList;
    SetStatus(bShowToolList ? TEXT("Tool list shown.") : TEXT("Tool list hidden."));
    return FReply::Handled();
}

#undef LOCTEXT_NAMESPACE
