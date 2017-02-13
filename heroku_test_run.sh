# Push
git push heroku master

# Spin up one instance
heroku ps:scale web=1

# Stream the logs until Ctrl-C
heroku logs --source app --tail

# Shutdown the instance
heroku ps:scale web=0
