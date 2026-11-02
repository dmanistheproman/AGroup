/* Fictional records for the AGroup interface prototype. */
window.AG={
projects:[
{id:1,title:'The quiet everyday',firm:'Form & Field',style:'Japandi',type:'HDB',location:'Tampines',price:58000,area:'93 m²',image:'living',materials:'Oak veneer, limewash walls, linen upholstery',summary:'Soft textures, warm oak and room to breathe. A considered home designed around the simple rituals of daily life.'},
{id:2,title:'Made for gathering',firm:'Common Ground',style:'Contemporary',type:'Condominium',location:'Queenstown',price:82000,area:'112 m²',image:'kitchen',materials:'Quartz worktops, engineered timber, brushed steel',summary:'An open kitchen and generous gathering spaces bring the family together, from weekday breakfasts to long weekend dinners.'},
{id:3,title:'A softer kind of city',firm:'Studio Sunday',style:'Scandinavian',type:'HDB',location:'Punggol',price:45000,area:'88 m²',image:'dining',materials:'Birch plywood, matte tiles, cotton textiles',summary:'Light-filled corners and honest materials make compact city living feel open, calm and personal.'},
{id:4,title:'An unhurried retreat',firm:'Form & Field',style:'Minimalist',type:'Condominium',location:'Bishan',price:69000,area:'104 m²',image:'bedroom',materials:'Natural oak, wool rugs, textured plaster',summary:'A restful palette and practical storage create a quiet retreat from the pace of the city.'},
{id:5,title:'Warmth in the details',firm:'Studio Sunday',style:'Japandi',type:'HDB',location:'Queenstown',price:52000,area:'90 m²',image:'kitchen',materials:'Oak cabinetry, porcelain tiles, rattan details',summary:'A practical family home with soft silhouettes, layered textures and plenty of natural warmth.'},
{id:6,title:'Space to come together',firm:'Common Ground',style:'Contemporary',type:'Landed',location:'Bishan',price:128000,area:'185 m²',image:'living',materials:'Travertine accents, timber flooring, woven fabrics',summary:'Connected living spaces give this multigenerational home a generous, welcoming heart.'}
],
firms:[{name:'Form & Field',initials:'FF',style:'Japandi & Minimalist',rating:'4.8',reviews:12,years:8,location:'East Singapore',text:'Quiet architecture and natural materials, designed around the way you live.'},{name:'Common Ground',initials:'CG',style:'Contemporary',rating:'4.7',reviews:9,years:6,location:'Central Singapore',text:'Spaces for connection, with thoughtful planning and a confident sense of character.'},{name:'Studio Sunday',initials:'SS',style:'Scandinavian & Japandi',rating:'4.9',reviews:15,years:5,location:'North-east Singapore',text:'Approachable design, playful details and easy everyday living.'}],
escape(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));},
money(v){return 'S$'+Number(v).toLocaleString('en-SG');},
read(key,fallback){try{return JSON.parse(localStorage.getItem('agroup-'+key))??fallback;}catch{return fallback;}},
write(key,val){try{localStorage.setItem('agroup-'+key,JSON.stringify(val));return true;}catch{return false;}},
toast(message){const el=document.getElementById('toast');el.textContent=message;el.classList.add('show');clearTimeout(window.agToast);window.agToast=setTimeout(()=>el.classList.remove('show'),3500);}
};
