BUILTIN_YARA_RULES = {
    "Mimikatz": """rule Mimikatz_Generic {
    meta:
        description = "Detects Mimikatz credential dumper"
        author      = "IOC Analyzer"
        severity    = "critical"
    strings:
        $s1 = "mimikatz" ascii nocase
        $s2 = "sekurlsa" ascii nocase
        $s3 = "lsadump" ascii nocase
        $s4 = "kerberos::list" ascii nocase
        $s5 = "privilege::debug" ascii nocase
        $b1 = { 6D 69 6D 69 6B 61 74 7A }
    condition:
        2 of ($s*) or $b1
}""",

    "Meterpreter": """rule Meterpreter_Shellcode {
    meta:
        description = "Detects Metasploit Meterpreter shellcode patterns"
        author      = "IOC Analyzer"
        severity    = "critical"
    strings:
        $h1 = { FC E8 8? 00 00 00 }
        $h2 = { 60 89 E5 31 D2 64 }
        $s1 = "metsrv" ascii nocase
        $s2 = "ReflectiveLoader" ascii
        $s3 = "meterpreter" ascii nocase
        $s4 = { 4D 65 74 65 72 70 72 65 74 65 72 }
    condition:
        any of ($h*) or 2 of ($s*)
}""",

    "CobaltStrike": """rule CobaltStrike_Beacon {
    meta:
        description = "Detects Cobalt Strike Beacon artifacts"
        author      = "IOC Analyzer"
        severity    = "critical"
    strings:
        $s1 = "%s as %s\\\\%s: %d" ascii
        $s2 = "beacon.dll" ascii nocase
        $s3 = "cobaltstrike" ascii nocase
        $h1 = { 00 68 74 74 70 73 3F 00 }
        $h2 = { 69 68 69 68 69 6B }
        $cfg1 = { 00 01 00 01 00 02 }
    condition:
        1 of ($s*) or any of ($h*) or $cfg1
}""",

    "PowerShell_Encoded": """rule PowerShell_Encoded_Command {
    meta:
        description = "Detects PowerShell encoded/obfuscated execution"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $s1 = "-EncodedCommand" ascii nocase
        $s2 = "-enc " ascii nocase
        $s3 = "powershell -e " ascii nocase
        $s4 = "IEX(" ascii nocase
        $s5 = "Invoke-Expression" ascii nocase
        $s6 = "FromBase64String" ascii nocase
        $s7 = "-WindowStyle Hidden" ascii nocase
        $s8 = "bypass" ascii nocase
    condition:
        3 of them
}""",

    "Ransomware_Generic": """rule Ransomware_Generic_Indicators {
    meta:
        description = "Generic ransomware behavioral indicators"
        author      = "IOC Analyzer"
        severity    = "critical"
    strings:
        $ext1 = ".encrypted" ascii nocase
        $ext2 = ".locked" ascii nocase
        $ext3 = ".crypto" ascii nocase
        $ext4 = "YOUR_FILES_ENCRYPTED" ascii nocase
        $note1 = "DECRYPT" ascii nocase
        $note2 = "RANSOM" ascii nocase
        $note3 = "bitcoin" ascii nocase
        $note4 = "recover your files" ascii nocase
        $api1 = "CryptEncrypt" ascii
        $api2 = "CryptGenRandom" ascii
        $vss1 = "vssadmin delete shadows" ascii nocase
        $vss2 = "wbadmin delete" ascii nocase
    condition:
        2 of ($ext*) or 3 of ($note*) or (any of ($vss*) and 1 of ($api*))
}""",

    "WannaCry": """rule WannaCry_Ransomware {
    meta:
        description = "Detects WannaCry / WannaCrypt ransomware"
        author      = "IOC Analyzer"
        severity    = "critical"
    strings:
        $s1 = "WannaCry" ascii nocase
        $s2 = "WannaDecryptor" ascii nocase
        $s3 = "tasksche.exe" ascii nocase
        $s4 = "@WanaDecryptor@.exe" ascii
        $s5 = "msg/m_chinese(simplified).wnry" ascii
        $h1 = { ED 1D 3C 15 }
        $kill = "MsWinZonesCacheCounterMutexA" ascii
    condition:
        2 of ($s*) or $h1 or $kill
}""",

    "Emotet": """rule Emotet_Trojan {
    meta:
        description = "Detects Emotet banking trojan indicators"
        author      = "IOC Analyzer"
        severity    = "critical"
    strings:
        $s1 = "emotet" ascii nocase
        $s2 = "geodo" ascii nocase
        $reg1 = "SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run" ascii nocase
        $net1 = { 47 45 54 20 2F }
        $enc1 = { C7 45 ?? 45 6D 6F 74 }
        $str1 = "UpdateTask" ascii
        $str2 = "svchost.exe" ascii
    condition:
        any of ($s*) or 2 of ($str*)
}""",

    "AgentTesla": """rule AgentTesla_Stealer {
    meta:
        description = "Detects Agent Tesla keylogger/stealer"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $s1 = "AgentTesla" ascii nocase
        $s2 = "agent tesla" ascii nocase
        $s3 = "SmtpClient" ascii
        $s4 = "GetAsyncKeyState" ascii
        $s5 = "Keylogger" ascii nocase
        $s6 = "clipboard" ascii nocase
        $smtp = { 53 4D 54 50 }
    condition:
        2 of ($s*) or ($smtp and 2 of ($s*))
}""",

    "Njrat": """rule NjRat_RAT {
    meta:
        description = "Detects NjRat Remote Access Trojan"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $s1 = "njRAT" ascii nocase
        $s2 = "Bladabindi" ascii nocase
        $s3 = "|'|'|" ascii
        $s4 = "njq8" ascii nocase
        $net = { 7C 27 7C 27 7C }
        $mutex = "fuckav" ascii nocase
    condition:
        any of ($s*) or $net or $mutex
}""",

    "Keylogger_Generic": """rule Keylogger_Generic {
    meta:
        description = "Generic keylogger API usage patterns"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $api1 = "SetWindowsHookEx" ascii
        $api2 = "GetAsyncKeyState" ascii
        $api3 = "GetKeyState" ascii
        $api4 = "KeyboardProc" ascii
        $api5 = "WH_KEYBOARD_LL" ascii
        $log1 = "keylog" ascii nocase
        $log2 = "keystroke" ascii nocase
    condition:
        3 of ($api*) or (2 of ($api*) and 1 of ($log*))
}""",

    "ProcessInjection": """rule Process_Injection_Techniques {
    meta:
        description = "Detects common process injection API patterns"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $api1 = "VirtualAllocEx" ascii
        $api2 = "WriteProcessMemory" ascii
        $api3 = "CreateRemoteThread" ascii
        $api4 = "NtCreateThreadEx" ascii
        $api5 = "RtlCreateUserThread" ascii
        $api6 = "SetThreadContext" ascii
        $api7 = "QueueUserAPC" ascii
    condition:
        3 of them
}""",

    "DLL_Sideloading": """rule DLL_Sideloading_Indicators {
    meta:
        description = "Detects potential DLL sideloading artifacts"
        author      = "IOC Analyzer"
        severity    = "medium"
    strings:
        $s1 = "LoadLibrary" ascii
        $s2 = "GetProcAddress" ascii
        $s3 = "DllMain" ascii
        $s4 = "DllRegisterServer" ascii
        $path1 = "\\\\AppData\\\\Roaming\\\\" ascii nocase
        $path2 = "\\\\AppData\\\\Local\\\\Temp\\\\" ascii nocase
        $path3 = "%TEMP%" ascii nocase
    condition:
        ($s1 and $s2 and $s3) and any of ($path*)
}""",

    "WebShell_PHP": """rule WebShell_PHP {
    meta:
        description = "Detects PHP web shells"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $s1 = "eval(base64_decode" ascii nocase
        $s2 = "eval(gzinflate" ascii nocase
        $s3 = "eval(str_rot13" ascii nocase
        $s4 = "system($_" ascii nocase
        $s5 = "exec($_" ascii nocase
        $s6 = "passthru($_" ascii nocase
        $s7 = "shell_exec($_" ascii nocase
        $s8 = "<?php eval" ascii nocase
    condition:
        any of them
}""",

    "Suspicious_Office_Macro": """rule Suspicious_Office_Macro {
    meta:
        description = "Detects potentially malicious Office macros"
        author      = "IOC Analyzer"
        severity    = "medium"
    strings:
        $s1 = "AutoOpen" ascii
        $s2 = "AutoExec" ascii
        $s3 = "Document_Open" ascii
        $s4 = "Shell(" ascii nocase
        $s5 = "WScript.Shell" ascii nocase
        $s6 = "powershell" ascii nocase
        $s7 = "cmd.exe" ascii nocase
        $s8 = "CreateObject" ascii
        $s9 = "Chr(" ascii
    condition:
        (any of ($s1,$s2,$s3)) and 3 of ($s4,$s5,$s6,$s7,$s8,$s9)
}""",

    "Network_Recon": """rule Network_Recon_Tools {
    meta:
        description = "Detects network reconnaissance tool signatures"
        author      = "IOC Analyzer"
        severity    = "medium"
    strings:
        $nmap = "nmap" ascii nocase
        $masscan = "masscan" ascii nocase
        $netcat = "netcat" ascii nocase
        $s1 = "port scan" ascii nocase
        $s2 = "SYN scan" ascii nocase
        $s3 = "OS detection" ascii nocase
        $s4 = "-sS " ascii
        $s5 = "-p 1-65535" ascii nocase
    condition:
        any of ($nmap,$masscan,$netcat) or 2 of ($s*)
}""",

    "Credential_Harvesting": """rule Credential_Harvesting {
    meta:
        description = "Detects credential harvesting patterns"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $s1 = "password" ascii nocase
        $s2 = "credential" ascii nocase
        $s3 = "LSASS" ascii nocase
        $s4 = "SAM database" ascii nocase
        $s5 = "hashdump" ascii nocase
        $api1 = "LsaRetrievePrivateData" ascii
        $api2 = "SamConnect" ascii
        $api3 = "CryptUnprotectData" ascii
    condition:
        2 of ($api*) or (3 of ($s*) and 1 of ($api*))
}""",

    "Persistence_Registry": """rule Persistence_Registry {
    meta:
        description = "Detects registry-based persistence mechanisms"
        author      = "IOC Analyzer"
        severity    = "medium"
    strings:
        $r1 = "CurrentVersion" ascii nocase
        $r2 = "RunOnce" ascii nocase
        $r3 = "Winlogon" ascii nocase
        $api1 = "RegSetValueEx" ascii
        $api2 = "RegCreateKey" ascii
    condition:
        any of ($r*) and any of ($api*)
}""",

    "UAC_Bypass": """rule UAC_Bypass_Techniques {
    meta:
        description = "Detects common UAC bypass techniques"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $s1 = "eventvwr.exe" ascii nocase
        $s2 = "fodhelper.exe" ascii nocase
        $s3 = "sdclt.exe" ascii nocase
        $s4 = "cmstp.exe" ascii nocase
        $s5 = "bypassuac" ascii nocase
        $reg = "ms-settings" ascii nocase
        $api = "ShellExecute" ascii
    condition:
        (2 of ($s*)) or ($reg and $api)
}""",

    "Lateral_Movement": """rule Lateral_Movement_SMB {
    meta:
        description = "Detects lateral movement via SMB/WMI"
        author      = "IOC Analyzer"
        severity    = "high"
    strings:
        $s1 = "psexec" ascii nocase
        $s2 = "wmiexec" ascii nocase
        $s3 = "smbexec" ascii nocase
        $s4 = "pass-the-hash" ascii nocase
        $s5 = "IPC$" ascii
        $smb = { 5C 00 5C 00 }
        $wmi1 = "Win32_Process" ascii
        $wmi2 = "WMI" ascii
    condition:
        any of ($s*) or (2 of ($wmi*) and $smb)
}""",

    "Anti_Analysis": """rule Anti_Analysis_Evasion {
    meta:
        description = "Detects anti-debugging and anti-analysis techniques"
        author      = "IOC Analyzer"
        severity    = "medium"
    strings:
        $d1 = "IsDebuggerPresent" ascii
        $d2 = "CheckRemoteDebuggerPresent" ascii
        $d3 = "NtQueryInformationProcess" ascii
        $vm1 = "VMware" ascii nocase
        $vm2 = "VirtualBox" ascii nocase
        $vm3 = "VBOX" ascii nocase
        $sand1 = "SbieDll.dll" ascii
        $sand2 = "sbiedll" ascii nocase
    condition:
        2 of ($d*) or 2 of ($vm*) or any of ($sand*)
}""",

    "EICAR_Test": """rule EICAR_Test_File {
    meta:
        description = "Detects EICAR antivirus test file"
        author      = "IOC Analyzer"
        severity    = "low"
    strings:
        $eicar = "EICAR-STANDARD-ANTIVIRUS-TEST-FILE" ascii
        $eicar2 = "X5O!P%@AP" ascii
    condition:
        any of them
}""",
}

AI_SYSTEM = """Ты — старший аналитик по кибербезопасности и эксперт по анализу угроз.

Твои компетенции:
1. Написание и разбор YARA правил любой сложности
2. Анализ индикаторов компрометации (хэши, IP, домены, процессы)
3. Техники атак MITRE ATT&CK и методы детектирования
4. Реагирование на инциденты и проведение triage
5. Разбор отчётов и артефактов — CSV, логи, результаты сканирований

При генерации YARA правил всегда включай секцию meta с полями description, author, severity.
Severity: critical / high / medium / low

Отвечай на русском языке, чётко и по делу."""

QUICK_PROMPTS = [
    "Напиши YARA правило для обнаружения Mimikatz",
    "Объясни технику DLL Sideloading (MITRE T1574.002)",
    "Как анализировать подозрительный процесс?",
    "Напиши YARA правило для PowerShell-стеганографии",
    "Что такое IoC и как их собирать?",
    "Как правильно составить отчёт об инциденте?",
    "Объясни разницу между YARA и Sigma правилами",
    "Как провести triage при обнаружении ransomware?",
]
