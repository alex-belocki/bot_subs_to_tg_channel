from flask_admin.contrib.sqla import ModelView
from flask_login import current_user


class SubscriptionView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated

    column_display_pk = True
    column_list = (
        'id', 'user_id', 'channel_id', 'start_at', 'end_at', 
        'status', 'created_at', 'revoked_at'
    )
    column_searchable_list = ('user_id', 'channel_id', 'status')
    column_filters = ('status', 'start_at', 'end_at')
    column_default_sort = ('id', True)

    column_labels = dict(
        id='ID',
        user_id='ID Пользователя',
        channel_id='ID Канала',
        start_at='Дата начала',
        end_at='Дата окончания',
        status='Статус',
        created_at='Дата создания',
        updated_at='Дата обновления',
        revoked_at='Дата отзыва',
        revoked_reason='Причина отзыва'
    )

    column_descriptions = dict(
        status='active - активна, expired - истекла, revoked - отозвана'
    )

    form_columns = (
        'user_id', 'channel_id', 'start_at', 'end_at', 
        'status', 'revoked_at', 'revoked_reason'
    )


class SubscriptionAccessView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated

    column_display_pk = True
    column_list = (
        'id', 'subscription_id', 'invite_link', 'expire_at', 
        'member_limit', 'created_at', 'used_at'
    )
    column_searchable_list = ('subscription_id', 'invite_link')
    column_filters = ('expire_at', 'used_at')
    column_default_sort = ('id', True)

    column_labels = dict(
        id='ID',
        subscription_id='ID Подписки',
        invite_link='Ссылка-приглашение',
        expire_at='Истекает',
        member_limit='Лимит участников',
        created_at='Дата создания',
        used_at='Дата использования'
    )

    form_columns = (
        'subscription_id', 'invite_link', 'expire_at', 
        'member_limit', 'used_at'
    )
