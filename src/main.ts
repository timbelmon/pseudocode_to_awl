import { pseudocodeToAwl, awlToPseudocode } from './translator';

const pseudo = document.getElementById('pseudocode') as HTMLTextAreaElement;
const awl = document.getElementById('awl') as HTMLTextAreaElement;

let lockLeft = false;
let lockRight = false;

pseudo.addEventListener('input', () => {
  if (lockLeft) return;
  const res = pseudocodeToAwl(pseudo.value);
  lockRight = true;
  awl.value = res;
  lockRight = false;
});

awl.addEventListener('input', () => {
  if (lockRight) return;
  const res = awlToPseudocode(awl.value);
  lockLeft = true;
  pseudo.value = res;
  lockLeft = false;
});
