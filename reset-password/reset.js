import {createClient} from 'https://esm.sh/@supabase/supabase-js@2.116.0?bundle';
import {REDIRECT,recoveryKind,passwordIssue} from './policy.mjs';
const kind=recoveryKind(location.hash,location.search),$=s=>document.querySelector(s);
const auth=createClient('https://epumcdxfkcujulqrcjrw.supabase.co','sb_publishable_KPadXg3RKth3SGsAuXzebA_OylGgtpf',{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true,flowType:'implicit'}});
let recovery=false,busy=false;
function message(text,error=false){$('#recovery-status').textContent=text;$('#recovery-status').classList.toggle('error',error);}
$('#request-reset').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;e.submitter.disabled=true;try{const {error}=await auth.auth.resetPasswordForEmail(e.target.email.value.trim(),{redirectTo:REDIRECT});if(error)throw error;message('若此信箱已註冊，你將收到重設連結。請查看收件匣與垃圾郵件；點開最新一封信中的連結。');}catch{message('目前無法寄送，請稍後再試。短時間重複要求可能受到限制。',true);}finally{busy=false;e.submitter.disabled=false;}};
$('#set-password').onsubmit=async e=>{e.preventDefault();if(busy||!recovery)return;const issue=passwordIssue(e.target.password.value,e.target.confirm.value);if(issue)return message(issue,true);busy=true;e.submitter.disabled=true;try{const {error}=await auth.auth.updateUser({password:e.target.password.value});if(error)throw error;e.target.reset();recovery=false;e.target.hidden=true;message('密碼已更新。請返回管理後臺登入。');await auth.auth.signOut({scope:'local'});}catch{message('無法更新密碼。請確認密碼符合要求；連結過期時，請重新寄送重設信。',true);}finally{busy=false;e.submitter.disabled=false;}};
if(kind==='expired'){history.replaceState(null,'',location.pathname);message('重設連結已失效或已使用，請重新寄送。',true);}
if(kind==='recovery'){
 $('#request-reset').hidden=true;message('正在驗證重設連結…');
 try{const {data,error}=await auth.auth.getSession();history.replaceState(null,'',location.pathname);if(error||!data.session)throw new Error('invalid');const user=await auth.auth.getUser();if(user.error||!user.data.user)throw new Error('invalid');recovery=true;$('#set-password').hidden=false;$('#recovery-description').textContent='請設定新的登入密碼，至少 10 個字元。';message('重設連結已驗證。');}catch{history.replaceState(null,'',location.pathname);$('#request-reset').hidden=false;message('無法驗證重設連結，請重新寄送並使用最新的連結。',true);}
}
