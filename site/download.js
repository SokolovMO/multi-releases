const root=document.querySelector('[data-app]');
async function load(){
 try{
 const response=await fetch('releases.json',{cache:'no-store'});if(!response.ok)throw new Error();
 const releases=await response.json();
 const app=root.dataset.app;
 const valid=releases.filter(r=>r.app===app&&r.architecture==='arm64'&&/^https:\/\/github\.com\/SokolovMO\/multi-releases\/releases\/download\//.test(r.url)&&/^[a-f0-9]{64}$/.test(r.sha256));
 const stable=valid.find(r=>r.channel==='stable');const beta=valid.find(r=>r.channel==='beta');
 root.replaceChildren();
 if(!stable&&!beta){root.textContent='подписанный выпуск пока не опубликован. ссылка появится после приёмки.';return;}
 for(const [label,r] of [['stable',stable],['beta · пилот',beta]]){
 if(!r)continue;const section=document.createElement('section');const title=document.createElement('h2');title.textContent=label;section.append(title);
 const link=document.createElement('a');link.className='download';link.href=r.url;link.textContent=`скачать ${app} ${r.version} (${r.build})`;section.append(link);
 const requirements=document.createElement('p');requirements.textContent=`Apple Silicon · требуется macOS ${r.minimum_macos} или новее. совместимость отдельных приложений и полей ввода описана в заметках выпуска.`;section.append(requirements);
 const notes=document.createElement('a');notes.href=r.release_url;notes.textContent='изменения, ограничения и исходники';section.append(notes);
 const hash=document.createElement('p');hash.className='hash';hash.textContent=`SHA-256: ${r.sha256}`;section.append(hash);root.append(section);
 }
 }catch{root.textContent='сведения о выпусках пока недоступны. попробуйте открыть страницу позже.';}
}
load();
