# SnowLuma 协议覆盖表

## Action 覆盖

| 分类 | 数量 | Action |
|---|---:|---|
| 已封装 @API | 166 | add_group_tag, bot_exit, can_send_image, can_send_record, cancel_group_todo, check_url_safely, clean_cache, clean_stream_temp_file, click_inline_keyboard_button, comment_qzone, complete_group_todo, create_collection, create_flash_task, create_group_file_folder, del_group_album_media, delete_essence_msg, delete_friend, delete_group_file, delete_group_folder, delete_group_tag, delete_msg, delete_qzone_msg, do_group_album_comment, download_file, download_file_image_stream, download_file_record_stream, download_file_stream, download_fileset, fetch_custom_face, fetch_emoji_like, fetch_sys_faces, forward_friend_single_msg, forward_group_single_msg, friend_poke, get_ai_characters, get_ai_record, get_clientkey, get_collection_list, get_cookies, get_credentials, get_csrf_token, get_doubt_friends_add_request, get_emoji_likes, get_essence_msg_list, get_file, get_fileset_id, get_fileset_info, get_flash_file_list, get_flash_file_url, get_forward_msg, get_friend_list, get_friend_msg_history, get_friends_with_category, get_group_admin_settings, get_group_album_media_list, get_group_at_all_remain, get_group_detail_info, get_group_file_system_info, get_group_file_url, get_group_files_by_folder, get_group_honor_info, get_group_ignore_add_request, get_group_ignored_notifies, get_group_info, get_group_info_ex, get_group_list, get_group_member_info, get_group_member_list, get_group_msg_history, get_group_root_files, get_group_share_link, get_group_shut_list, get_group_system_msg, get_group_tags, get_group_todo_list, get_image, get_login_info, get_mini_app_ark, get_msg, get_msg_emoji_likes, get_online_clients, get_private_file_url, get_profile_like, get_qun_album_list, get_qzone_feeds, get_qzone_msg_detail, get_qzone_msg_list, get_recent_contact, get_record, get_rkey, get_rkey_server, get_share_link, get_status, get_stranger_info, get_unidirectional_friend_list, get_version_info, group_poke, like_qzone, mark_group_msg_as_read, mark_msg_as_read, mark_private_msg_as_read, move_group_file, nc_get_packet_status, nc_get_rkey, nc_get_user_status, ocr_image, rename_group_file, search_sys_faces, send_ark_share, send_custom_face, send_flash_msg, send_forward_msg, send_group_ai_record, send_group_ark_share, send_group_forward_msg, send_group_msg, send_group_sign, send_like, send_msg, send_packet, send_poke, send_private_forward_msg, send_private_msg, send_qzone_msg, set_diy_online_status, set_doubt_friends_add_request, set_essence_msg, set_friend_add_request, set_friend_remark, set_friends_category, set_group_add_option, set_group_add_request, set_group_admin, set_group_album_media_like, set_group_ban, set_group_card, set_group_kick, set_group_kick_members, set_group_leave, set_group_member_permissions, set_group_name, set_group_portrait, set_group_reaction, set_group_remark, set_group_robot_add_option, set_group_search, set_group_sign, set_group_special_title, set_group_todo, set_group_whole_ban, set_input_status, set_msg_emoji_like, set_online_status, set_qq_avatar, set_qq_profile, set_restart, set_self_longnick, test_download_stream, trans_group_file, translate_en2zh, unlike_qzone, upload_file_stream, upload_forward_msg, upload_group_file, upload_image_to_qun_album, upload_private_file |
| 内部使用 | 0 |  |
| 按设计不支持 | 9 | cancel_online_file, get_guild_list, get_guild_service_profile, get_online_file_msg, get_robot_uin_range, receive_online_file, refuse_online_file, send_online_file, send_online_folder |
| 未使用 | 40 | .get_word_slices, .ocr_image, .send_packet, _del_group_notice, _get_friend_dress, _get_group_notice, _get_model_show, _mark_all_as_read, _send_group_notice, _set_model_show, add_custom_face, cancel_group_album_media_like, delete_custom_face, delete_flash_file, delete_group_file_folder, fetch_custom_face_detail, fetch_face_entity, fetch_ptt_text, fetch_super_face_id, get_group_album_list, get_group_signed_list, get_ptt_text, get_record_text, list_filesets, modify_custom_face, move_custom_face_to_front, rename_flash_file, rename_group_file_folder, request_decrypt_key, send_tuwen_ark, set_group_anonymous, set_group_anonymous_ban, set_group_member_invite_policy, set_group_new_member_history_visibility, set_qzone_ban, set_qzone_msg_right, share_group_ex, share_peer, upload_foward_msg, upload_video_to_qun_album |

## Event 覆盖

| 类型 | 映射 |
|---|---|
| notice_type `bot_offline` | 普通 MaiBot 通知（系统文本） |
| notice_type `essence` | 普通 MaiBot 通知（系统文本） |
| notice_type `friend_add` | 普通 MaiBot 通知（系统文本） |
| notice_type `friend_recall` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_admin` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_ban` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_card` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_decrease` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_increase` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_msg_emoji_like` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_recall` | 普通 MaiBot 通知（系统文本） |
| notice_type `group_upload` | 普通 MaiBot 通知（系统文本） |
| notice_type `notify` | 普通 MaiBot 通知（系统文本） |
| notify `poke` | 普通 MaiBot 通知（输入状态由配置控制） |
| notify `group_name` | 普通 MaiBot 通知（输入状态由配置控制） |
| notify `title` | 普通 MaiBot 通知（输入状态由配置控制） |
| notify `input_status` | 普通 MaiBot 通知（输入状态由配置控制） |
| notify `profile_like` | 普通 MaiBot 通知（输入状态由配置控制） |
| post_type `message` | 入站消息编解码器 |
| post_type `notice` | 通知编解码器 |
| post_type `meta_event` | 运行态与心跳观测 |
| post_type 未知 | debug 后跳过 |

## Segment 覆盖

| 类型 | 入站 | 出站 | 降级策略 |
|---|---|---|---|
| `at` | 支持 | 支持 | — |
| `face` | 支持 | 支持 | — |
| `file` | 支持 | 支持 | — |
| `flash_file` | 支持 | 文本降级 | 文本+文件名/大小/URL，不下载 |
| `forward` | 支持 | 支持 | — |
| `image` | 支持 | 支持 | — |
| `inline_keyboard` | 支持 | 文本降级 | [内联键盘] |
| `json` | 支持 | 支持 | — |
| `markdown` | 支持 | 文本降级 | — |
| `mface` | 支持 | 文本降级 | 摘要或类型 ID 文本 |
| `poke` | 支持 | 文本降级 | [戳一戳] |
| `record` | 支持 | 支持 | — |
| `reply` | 支持 | 支持 | — |
| `text` | 支持 | 支持 | — |
| `video` | 支持 | 支持 | — |
| `xml` | 支持 | 支持 | — |

数据来源：SnowLuma 源码注册表 + 官方 OpenAPI spec；事件字段据事件转换实现核对。
重新生成：`uv run python scripts/check_snowluma_coverage.py --markdown docs/snowluma-coverage.md`
SnowLuma 版本：源码副本 v1.14.x。
