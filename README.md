# Flag Tracking Script

This script detects specific channel point redemptions and logs the redemption information to a json file in the script directory.

## Installing

This script was built for use with Streamlabs Chatbot.
Follow instructions on how to install custom script packs at:
https://github.com/StreamlabsSupport/Streamlabs-Chatbot/wiki/Prepare-&-Import-Scripts

Once installed you will need to provide an oAuth token. You can get one by clicking the Get Token button in script settings.
This button also exists in the streamlabs chatbot UI. Make sure you don't show this token on stream, it is as sensitive
as your stream key!

If you are using Google Sheets, you will need to create a Google Sheet and then share the sheet with twitchredemptiontrackerservice@twitchredemptiontracker.iam.gserviceaccount.com, including Edit permissions.
Finally, add the Spreadsheet ID and the Sheet Name to the script settings. The Spreadsheet ID can be found in the URL when you are on the spreadsheet. The Sheet Name is on the tab at the bottom left.

## Use

### Options

-Accept Commands Only When Live: Toggles the ability to respond to chat commands when offline. (Default: True)

-Command Name: Customizes the command used to display and modify your queue. (Default: queue)

-Queue Display Limit: Limits the !<CommandName> display to X queue entries. (Default: 10)

-Redemption Names: The name of the redemption the script should listen for and log from. (No default)

-Reconnection Attempts: The number of times the script can attempt to reconnect to Twitch when the connection is lost. (Default: 5)

-Token Validity Check Interval: The number of minutes between automatic checks to see if the Twitch oAuth token is still valid. (Default: 10, 0 = Off).

-Twitch oAuth Token: Your Twitch oAuth token to authenticate the script's redemption listener. (No default)

-Enable Google Sheets: The toggle to enable usage of Google Sheets. (Default: Off)

-Google Sheets ID: The id of your Google Sheet. To get your ID, visit your Google Sheet. The ID will be the part in the address bar after "/d/" but before the next "/". (No default)

-Worksheet Name: The Sheet the script should update. To get your Sheet Name, visit your Google Sheet. The Sheet name is on the tabs at the bottom of the screen. (No default)

-If Game is Unknown, Display Redemption Message Instead: Any time the script would post a chat message and the game is Unknown, post the associated redemption message instead. (Default: Off)

-Enable Responses: Enables some additional chat responses when commands are used. (Default: True)

-Retain Logs Locally: Prevents the deletion of logs when the stream goes offline, the scripts get reloaded, or the chatbot shuts down. (Default: False)

### Permissions

-Help Display Permissions: The permission level required to display the script help functions. (Default: Everyone)

-Queue Display Permissions: The permission level required to display the queue or Google Sheet link. (Default: Everyone)

-Queue Find Permissions: The permission level required to use the Find subcommand to find a user in the queue. (Default: Everyone)

-Queue Remove Permissions: The permission level required to use the Remove subcommand to remove redemptions from the queue. (Default: Moderator)

-Queue Add Permissions: The permission level required to use the Add subcommand to add redemptions to the queue. (Default: Moderator)

-Queue Edit Permissions: The permission level required to use the Edit subcommand to edit existing redemptions in the queue. (Default: Moderator)

-Google Updater Manual Permissions: The permission level required to use the Updater subcommand to manually start the GoogleSheetsUpdater. (Default: Moderator)

-Version Check Permissions: The permission level required to use the Version subcommand to check for script updates. (Default: Moderator)

-Uptime Display Permissions: The permission level required to use the Uptime subcommand to display the script's connectivity status. (Default: Moderator)

-Manual Reconnect Permissions: The permission level required to use the Reconnect subcommand to attempt to reconnect the script to Twitch. (Default: Moderator)

-Twitch oAuth Token Expiry Display Permissions: The permission level required to use the Token subcommand to display information about the current Twitch oAuth Token. (Default: Moderator)

### Commands

-!{CommandName}: Displays the queue one line after another until the Queue Display Limit is hit.
  
-!{CommandName} remove {index}(,{index},...): Removes one or more entries from the queue based on index. When displaying the queue with !<CommandName>, the index is displayed to the left of the Username and Game information.
  
-!{CommandName} add Username:{Username}, Message:{Message}(, Game:{Game})(|Username:{Username}, Message:{Message}(, Game:{Game})|...): Adds one or more entries to the queue. Detects the username by looking for "Username:". Detects the message by looking for "Message:". Detects the game by looking for "Game:". If Username or Message are not found, the entry is not added to the queue and an error is logged. If Game is not found, the game is entered as "Unknown". To enter multiple sets of information, separate entries using the pipe "|" character.
  
-!{CommandName} edit {Index} {Username/Game/Message}:{NewValue}: Modifies the Username or Game or Message at the given index to the supplied value.

-!{CommandName} updater: Manually executes the GoogleSheetsUpdater to update the Google Sheet.

-!{CommandName} version: Displays the current script version as well as the latest version available on GitHub.

-!{CommandName} uptime: Displays the amount of time the script has been connected to Twitch, if it is connected.

-!{CommandName} reconnect: Manually attempts to reconnect to Twitch.

-!{CommandName} help: Displays the available subcommands and syntaxes of those subcommands.

## Authors

Crimdahl - [Twitch](https://www.twitch.tv/crimdahl), [GitHub](https://github.com/Crimdahl/)

IceyGlaceon - [Twitter](https://www.twitter.com/theiceyglaceon)

## References

This script makes use of TwitchLib's pubsub listener to detect the channel point redemptions. Go check out their repo at https://github.com/TwitchLib/TwitchLib for more info.

This script is based off of [IceyGlaceon's ChannelPointstoChannelCurrency script.](https://github.com/iceyglaceon/SLCB-Channel-Points-to-Channel-Currency/)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
