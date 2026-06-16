import 'package:im_flutter_sdk/im_flutter_sdk.dart';

class GroupMemberInfo {
  final String userId;
  final String memberId;
  final int joinedTs;
  final int joinTime;
  final EMGroupPermissionType role;
  final String? namecard;
  final String? nickname;
  final String? avatarUrl;
  final String? string;

  GroupMemberInfo(
    this.userId,
    this.joinedTs,
    this.role,
  )   : memberId = userId,
        joinTime = joinedTs,
        namecard = null,
        nickname = null,
        avatarUrl = null,
        string = null;

  GroupMemberInfo.fromJson(Map<String, dynamic> map)
      : userId = map["userId"],
        memberId = map["memberId"] ?? map["userId"],
        joinedTs = map["joinedTs"] ?? map["joinTime"],
        joinTime = map["joinTime"] ?? map["joinedTs"],
        namecard = map["namecard"],
        nickname = map["nickname"],
        avatarUrl = map["avatarUrl"],
        role = EMGroupPermissionTypeExtension.values(map["role"]),
        string = map["string"];

  Map toJson() {
    Map data = {};
    data["userId"] = userId;
    data["memberId"] = memberId;
    data["joinedTs"] = joinedTs;
    data["joinTime"] = joinTime;
    data["namecard"] = namecard;
    data["nickname"] = nickname;
    data["avatarUrl"] = avatarUrl;
    data["role"] = role.index;
    data["string"] = string;
    return data;
  }

  @override
  String toString() {
    return toJson().toString();
  }
}
