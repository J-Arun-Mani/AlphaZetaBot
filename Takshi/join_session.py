import logging
import telegram

from .constants import Label, Message
from .session import Session


class JoinSession(Session):
    def __init__(self, message, context):

        Session.__init__(self, message, context)
        self.group_id = None
        self.group_title = None
        self.groups = self.processor.get_groups(self.user.id)
        if context.args and context.args[0].startswith("join="):
            try:
                id = int(context.args[0].lstrip("join="))
            except (IndexError, ValueError):
                logging.error("Asked to join invalid id %s", id)
            else:
                self.do_join_group(id, edit=False)
        else:
            self.send_select_group()

    def do_join_group(self, id, edit=True):

        if edit:
            sender = self.base_message.edit_text
        else:
            sender = self.chat.send_message

        self.group_id = id
        self.group_title = self.groups.get(id, None)

        eligible = self.processor.get_eligible_for_link(id, self.user.id)
        link = self.processor.get_invite_link(id)
        prompt = self.processor.get_prompt(id)

        if prompt is None or link is None:
            self.send_group_not_found()
            return

        if eligible == -1:
            msg = sender(
                text=Message.PROMPT.format(PROMPT=prompt),
                parse_mode=telegram.ParseMode.HTML,
            )
        elif eligible == 0:
            buttons = [
                telegram.InlineKeyboardButton(
                    text=Label.JOIN_LINK.format(TITLE=self.group_title), url=link
                ),
                telegram.InlineKeyboardButton(
                    text=Label.REFRESH_LINK, callback_data=f"refJoin={id}"
                ),
            ]
            markup = telegram.InlineKeyboardMarkup.from_column(buttons)
            msg = sender(
                text=Message.LINK_CAUTION,
                parse_mode=telegram.ParseMode.HTML,
                reply_markup=markup,
            )
        else:
            msg = sender(
                text=Message.ALREADY_JOINED, parse_mode=telegram.ParseMode.HTML,
            )

        self.base_message = msg

    def handle_callback(self, query, context):

        data = query.data

        if not data:
            query.answer(text=Message.THANK_FOR_JOIN, show_alert=True)
        elif data.startswith("join="):
            try:
                id = int(data.lstrip("join="))
            except ValueError:
                logging.critical("Got non-integer id %s for join", id)
                self.chat.send_message(
                    text=Message.INVALID_QUERY, parse_mode=telegram.ParseMode.HTML
                )
            else:
                query.answer()
                self.do_join_group(id)
        elif data.startswith("refJoin="):
            try:
                id = int(data.lstrip("refJoin="))
            except ValueError:
                logging.critical("Got non-integer id %s for join", id)
                self.chat.send_message(
                    text=Message.INVALID_QUERY, parse_mode=telegram.ParseMode.HTML
                )
            else:
                query.answer(text=Message.LINK_REFRESHED, show_alert=True)
                self.do_join_group(id)
        else:
            query.answer()
            logging.critical("Got unexpected callback query %s", data)
            self.chat.send_message(
                text=Message.INVALID_QUERY, parse_mode=telegram.ParseMode.HTML
            )

    def handle_message(self, message, context):

        if not self.group_id:
            message.reply_text(
                text=Message.INVALID_MESSAGE, parse_mode=telegram.ParseMode.HTML
            )
            return

        moderate_id = self.processor.get_moderate_id(self.group_id)
        text = Message.FORWARD_MESSAGE.format(
            ID=self.user.id,
            USERNAME=self.user.username,
            NAME=f"{self.user.first_name} {self.user.last_name}",
            TEXT=message.text_html_urled,
        )
        self.bot.send_message(
            chat_id=moderate_id, text=text, parse_mode=telegram.ParseMode.HTML
        )
        self.chat.send_message(
            text=Message.SENT_TO_MODERATORS.format(TITLE=self.group_title),
            parse_mode=telegram.ParseMode.HTML,
        )

    def send_group_not_found(self):

        self.groups = self.processor.get_groups(self.user.id)
        text = Message.GROUP_NOT_FOUND.format(TITLE=self.group_title)
        self.base_message.edit_text(text=text, parse_mode=telegram.ParseMode.HTML)
        self.send_select_group()

    def send_select_group(self, edit=False):

        if edit:
            sender = self.base_message.edit_text
        else:
            sender = self.chat.send_message

        if not self.groups:
            sender(text=Message.NO_COMMON_GROUPS, parse_mode=telegram.ParseMode.HTML)
            return

        buttons = [
            telegram.InlineKeyboardButton(text=title, callback_data=f"join={id}")
            for id, title in self.groups.items()
        ]
        markup = telegram.InlineKeyboardMarkup.from_column(buttons)

        msg = sender(
            text=Message.JOIN_SELECT_GROUP,
            parse_mode=telegram.ParseMode.HTML,
            reply_markup=markup,
        )
        self.base_message = msg
