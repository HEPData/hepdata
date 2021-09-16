import HEPDATA from './hepdata_common.js'

window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']]
  }
};

HEPDATA.typeset = function(nodes=null) {
  try {
    window.MathJax.typeset(nodes);
  } catch(e) {
    // fail quietly
  }
};

(function () {
  var script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml-full.js';
  script.async = true;
  document.head.appendChild(script);
})();
