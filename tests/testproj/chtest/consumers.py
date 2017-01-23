

def ws_connect(message):
    message.reply_channel.send({
        'accept': True
    })


def ws_message(message):
    """Echoes messages back to the client"""
    if message['text'] == 'give reply channel':
        message.reply_channel.send({
            "text": str(message.reply_channel),
        })
    else:
        message.reply_channel.send({
            "text": message['text'],
        })
