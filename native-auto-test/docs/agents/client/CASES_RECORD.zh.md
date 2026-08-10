# Client 模块 Cases 总记录（按 API）

— 说明
- 本文件记录 Client 模块已覆盖用例（按 API 组织）。
- 每条 case 以全局序号编号；统计按“当前记录条目数”计算。
- 暂缓与 skip 项统一写 `CASES_DEFERRED.zh.md`。

## login

正常 cases
1. `tests/client/test_client.py::test_login_then_receive_offline_sync_event`
   重新登录后在同连接等待离线同步启动事件，验证登录成功后会触发基础同步回调。

异常 cases
2. `tests/client/test_client.py::test_client_login_invalid_password`
   使用错误密码登录，断言返回失败语义或可识别错误结构，避免误判为成功。

## getCurrentUser

正常 cases
3. `tests/client/test_client.py::test_client_get_current_user`
   在 session 已登录前提下调用 `getCurrentUser`，验证返回当前登录用户信息。

异常 cases
4. 无（当前测试集中未单独覆盖该 API 的异常入参）。
   说明：该 API 目前仅在已登录上下文使用，未单测非法登录态或参数异常路径。

## isDatabaseOpened

正常 cases
5. `tests/client/test_client_5_0_api.py::test_client_is_database_opened_after_session_login`
   SDK 5.0 登录后查询数据库打开状态，验证公开 API 返回稳定 bool，供消费侧判断本地 DB 是否可读取。

异常 cases
6. 无（当前 session fixture 默认已登录，未覆盖未登录态数据库状态）。

## onDataSyncStart / onDataSyncFinish / onDatabaseOpened

正常 cases
7. `tests/client/test_client_5_0_api.py::test_client_5_0_data_sync_and_database_callbacks_shape`
   SDK 5.0 数据同步与数据库打开回调经 EventBridge 透传时，校验 `type/errorCode/userId` 字段结构稳定；不同 dataSyncTypes 配置下允许回调不出现。

异常 cases
8. 无（回调类 API 当前仅验证结构，不构造异常事件）。

## 统计
- 当前记录 case 条目总数：`8`
