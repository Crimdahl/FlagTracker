# Flag Tracking Script

This script detects specific channel point redemptions and logs the redemption information to a json file in the script directory.

## Installing

This script was built for use with Streamlabs Chatbot.
Follow instructions on how to install custom script packs at:
https://github.com/StreamlabsSupport/Streamlabs-Chatbot/wiki/Prepare-&-Import-Scripts

Once installed you will need to provide an oAuth token. You can get one by clicking the Get Token button in script settings.
This button also exists in the streamlabs chatbot UI. Make sure you don't show this token on stream, it is as sensitive
as your stream key!

If you are using Google Sheets, you should be prompted to sign in to Google and then give permission for the script to modify 
the Google Sheet that corresponds to the Google Sheets ID supplied in the options. This stores a token in the script directory
so it does not need to ask for permissions every time.

## Use
### Options
-Accept Commands Only When Live: Toggles the ability to respond to chat commands when offline. (Default: True)

-Display Permissions: Sets the permissions required for a chatter to use !<CommandName> to display your queue. (Default: Everyone)
  
-Modify Permissions: Sets the permissions required for a chatter to modify your queue with subcommands. (Default: Moderator)

-Command Name: Customizes the command used to display and modify your queue. (Default: queue)

-Queue Display Limit: Limits the !<CommandName> display to X queue entries. (Default: 10)
  
-Title of Redemption: The name of the redemption the script should listen for and log from. (No default)

-Twitch oAuth Token: Your Twitch oAuth token to authenticate the redemption listener. (No default)

-Enable Google Sheets: The toggle to enable usage of Google Sheets

-Google Sheets ID: The id of your Google Sheet. To get your ID, visit your Google Sheet. The ID will be the part in the address bar after "/d/" but before the next "/"

-Worksheet Name: The Sheet the script should update. To get your Sheet Name, visit your Google Sheet. The Sheet name is on the tabs at the bottom of the screen.

-Enable Responses: Toggles the ability to post responses to your command directly in Twitch chat. (Default: True)

-Enable Debug: Toggles the ability to post debug messages in the Chatbot Logs. (Default: True)

### Commands
-!<CommandName>: Displays the queue one line after another until the Queue Display Limit is hit.
  
-!<CommandName> remove <index>(,<index>,...): Removes one or more entries from the queue based on index. When displaying the queue with !<CommandName>, the index is displayed to the left of the Username and Game information.
  
-!<CommandName> add Username:<Username>, Message:<Message>(, Game:<Game>)(|Username:<Username>, Message:<Message>(, Game:<Game>)|...): Adds one or more entries to the queue. Detects the username by looking for "Username:". Detects the message by looking for "Message:". Detects the game by looking for "Game:". If Username or Message are not found, the entry is not added to the queue and an error is logged. If Game is not found, the game is entered as "Unknown". To enter multiple sets of information, separate entries using the pipe "|" character.
  
-!<CommandName> edit <Index> <Username/Game/Message>:<NewValue>: Modifies the Username or Game or Message at the given index to the supplied value.

## Authors

Crimdahl - [Twitch](https://www.twitch.tv/crimdahl), [Twitter](https://www.twitter.com/crimdahl)

IceyGlaceon - [Twitch](https://www.twitch.tv/iceyglaceon), [Twitter](https://www.twitter.com/theiceyglaceon)

## References

This script makes use of TwitchLib's pubsub listener to detect the channel point redemptions. Go check out their repo at https://github.com/TwitchLib/TwitchLib for more info.

This script is based off of [IceyGlaceon's ChannelPointstoChannelCurrency script.](https://github.com/iceyglaceon/SLCB-Channel-Points-to-Channel-Currency/blob/master/ChannelPointsToChannelCurrency.zip?raw=true)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
