export const REDIRECT='https://pastfantast-glitch.github.io/ai-3d-daily/reset-password/';
export function recoveryKind(hash,search=''){
 const h=new URLSearchParams(hash.replace(/^#/,'')),q=new URLSearchParams(search.replace(/^\?/,''));
 if(h.has('error')||h.has('error_code')||q.has('error')||q.has('error_code'))return 'expired';
 return h.get('type')==='recovery'&&h.has('access_token')&&h.has('refresh_token')?'recovery':'request';
}
export function passwordIssue(password,confirm){if(password.length<10||password.length>128)return '請使用 10 至 128 個字元的密碼。';if(password!==confirm)return '兩次密碼不一致，請重新輸入。';return '';}
