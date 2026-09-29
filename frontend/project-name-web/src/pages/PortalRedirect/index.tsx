// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-07-27
import { Navigate } from 'react-router'

/**
 * 登录后的落点：一律是标书编制首页，管理员也不例外。
 *
 * 管理员首先也是写标书的人；管理面（审计、系统验证）是偶尔去的地方，
 * 从账号菜单的「系统管理」进入，而不是每次登录都先落在那里。
 */
export default function PortalRedirect() {
  return <Navigate to="/planner/writing" replace />
}
