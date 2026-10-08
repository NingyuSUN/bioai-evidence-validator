$ErrorActionPreference = 'Stop'
$run = $PSScriptRoot
$utf8 = New-Object System.Text.UTF8Encoding($false)
$info = New-Object System.Diagnostics.ProcessStartInfo
$info.FileName = 'C:\Users\n.sun\.local\bin\claude.exe'
$info.WorkingDirectory = $run
$info.UseShellExecute = $false
$info.RedirectStandardInput = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$info.Arguments = '-p --model claude-fable-5-1 --effort max --restricted --safe-mode --strict-mcp-config --tools "" --disable-slash-commands --permission-mode plan --permission-prompts none --no-session-persistence --prompt-suggestions false --output-format stream-json --verbose'
$info.EnvironmentVariables['CLAUDE_CODE_DISABLE_TERMINAL_TITLE'] = '1'
$info.EnvironmentVariables['ANTHROPIC_DEFAULT_HAIKU_MODEL'] = 'claude-fable-5-1'
$info.EnvironmentVariables['ANTHROPIC_SMALL_FAST_MODEL'] = 'claude-fable-5-1'
$info.EnvironmentVariables['CLAUDE_CODE_SUBAGENT_MODEL'] = 'claude-fable-5-1'
$info.EnvironmentVariables['CLAUDE_CODE_SUBAGENT_MODEL_FORCE'] = '1'
$p = New-Object System.Diagnostics.Process
$p.StartInfo = $info
$started = [DateTime]::UtcNow.ToString('o')
[void]$p.Start()
$status = @{state='RUNNING'; requested_model='claude-fable-5-1'; started_utc=$started; windows_pid=$p.Id; argv=$info.Arguments}
[System.IO.File]::WriteAllText((Join-Path $run 'execution.json'), ($status | ConvertTo-Json -Depth 5), $utf8)
$outFile = [System.IO.File]::Open((Join-Path $run 'raw.jsonl'), [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
$errFile = [System.IO.File]::Open((Join-Path $run 'stderr.txt'), [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
$outTask = $p.StandardOutput.BaseStream.CopyToAsync($outFile)
$errTask = $p.StandardError.BaseStream.CopyToAsync($errFile)
$promptBytes = [System.IO.File]::ReadAllBytes((Join-Path $run 'prompt.txt'))
$p.StandardInput.BaseStream.Write($promptBytes, 0, $promptBytes.Length)
$p.StandardInput.BaseStream.Flush()
$p.StandardInput.Close()
$timedOut = -not $p.WaitForExit(1800000)
if ($timedOut) { $p.Kill(); $p.WaitForExit() }
$outTask.Wait(); $errTask.Wait(); $outFile.Dispose(); $errFile.Dispose()
$status.state = if ($timedOut) {'TIMEOUT'} elseif ($p.ExitCode -eq 0) {'CLI_FINISHED_PENDING_MODEL_CHECK'} else {'FAILED'}
$status.exit_code = $p.ExitCode
$status.finished_utc = [DateTime]::UtcNow.ToString('o')
[System.IO.File]::WriteAllText((Join-Path $run 'execution.json'), ($status | ConvertTo-Json -Depth 5), $utf8)
$status | ConvertTo-Json -Depth 5
exit $p.ExitCode
