NameError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/patwit-police-portal/app.py", line 1220, in <module>
    if __name__ == "__main__": main()
                               ~~~~^^
File "/mount/src/patwit-police-portal/app.py", line 1217, in main
    traffic_module()
    ~~~~~~~~~~~~~~^^
File "/mount/src/patwit-police-portal/app.py", line 681, in traffic_module
    if do_search or do_filter:
       ^^^^^^^^^
