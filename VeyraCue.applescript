-- Compile beside the project as VeyraCue.app to launch without opening Terminal.
on run
    set appFolder to do shell script "/usr/bin/dirname " & quoted form of (POSIX path of (path to me))
    try
        do shell script "/bin/bash " & quoted form of (appFolder & "/silent_run.sh")
    on error startupError
        display dialog "VeyraCue could not start: " & startupError buttons {"OK"} default button "OK" with icon stop
    end try
end run
