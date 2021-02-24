
HEPDATA.render_loader = function (placement, events, options) {

  if (HEPDATA.interval == undefined) {
    clearInterval(HEPDATA.interval);
  }
  d3.select(placement).html('');
  var svg = d3.select(placement).append("svg").attr("width", options.width).attr("height", options.height).append("g");

  svg.append("rect").attr("width", options.width).attr("height", options.height).attr('fill', 'rgba(1,1,1,0)');


  var scaleX = d3.scale.linear()
    .domain([-100, 100])
    .range([0, options.width]);

  var scaleY = d3.scale.linear()
    .domain([-100, 100])
    .range([options.height, 0]);


  var line = d3.svg.line()
    .interpolate("basis")
    .x(function (d) {
      return scaleX(d.x);
    })
    .y(function (d) {
      return scaleY(d.y);
    });

  //draw detector rings
  svg.append("circle")
    .attr("cx", options.width / 2)
    .attr("cy", options.width / 2)
    .attr("r", options.width * .02)
    .attr("fill", "none")
    .attr("stroke", "#955BA5")
    .attr("stroke-width", options.width * .01)
    .attr("stroke-linecap", "round");

  svg.append("circle")
    .attr("cx", options.width / 2)
    .attr("cy", options.width / 2)
    .attr("r", options.width * .2)
    .attr("fill", "none")
    .attr("stroke", "#955BA5")
    .attr("stroke-width", options.width * .03)
    .attr("stroke-linecap", "round");


  var path = svg.selectAll("path")
    .data(events)
    .enter().append("path")
    .attr("d", function (d, i) {
      d['delay'] = i * 300;
      var line_path = [{x: 0, y: 0}, {x: d.x / 6, y: d.y + 2}, d];
      return line(line_path)
    })
    .attr("stroke", function (d) {
      return d.color;
    })
    .attr("stroke-width", options.width * .015)
    .attr("fill", "none")
    .attr("stroke-linecap", "round");

  function start_outgoing_animation(events) {

    path
      .attr("stroke-dasharray", function () {
        return d3.select(this).node().getTotalLength() + " " + d3.select(this).node().getTotalLength()
      })
      .attr("stroke-dashoffset", function () {
        return d3.select(this).node().getTotalLength();
      })
      .transition()
      .duration(1500)
      .delay(function (d) {
        return d.delay;
      })
      .ease("linear")
      .attr("stroke-dashoffset", 0);

    return path;
  }

  function start_incoming_animation(path) {
    path
      .transition()
      .delay(function (d) {
        return d.delay + 4000;
      })
      .duration(2000)
      .ease("linear")
      .attr("stroke-dashoffset", function () {
        return d3.select(this).node().getTotalLength();
      });
  }

  var path = start_outgoing_animation(events);
  start_incoming_animation(path);


  HEPDATA.interval = setInterval(function () {
    start_outgoing_animation(events);
    start_incoming_animation(path);
  }, 9000);
};

HEPDATA.render_about_animation = function (placement) {

  window.requestAnimFrame = function () {
    return (
      window.requestAnimationFrame ||
      window.webkitRequestAnimationFrame ||
      window.mozRequestAnimationFrame ||
      window.oRequestAnimationFrame ||
      window.msRequestAnimationFrame ||
      function (/* function */ callback) {
        window.setTimeout(callback, 2000 / 60);
      }
    );
  }();

  window.cancelAnimFrame = function () {
    return (
      window.cancelAnimationFrame ||
      window.webkitCancelAnimationFrame ||
      window.mozCancelAnimationFrame ||
      window.oCancelAnimationFrame ||
      window.msCancelAnimationFrame ||
      function (id) {
        window.clearTimeout(id);
      }
    );
  }();

  function SVGEl(el) {
    this.el = el;
    this.image = this.el.previousElementSibling;
    this.current_frame = 0;
    this.total_frames = 150;
    this.path = [];
    this.length = [];
    this.handle = 0;
    this.init();
  }

  SVGEl.prototype.init = function () {
    var self = this;
    [].slice.call(this.el.querySelectorAll('path')).forEach(function (path, i) {
      self.path[i] = path;
      var l = self.path[i].getTotalLength();
      self.length[i] = l;
      self.path[i].style.strokeDasharray = l + ' ' + l;
      self.path[i].style.strokeDashoffset = l;
    });
  };

  SVGEl.prototype.render = function () {
    if (this.rendered) return;
    this.rendered = true;
    this.draw();
  };

  SVGEl.prototype.draw = function () {
    var self = this,
      progress = this.current_frame / this.total_frames;
    if (progress > 1) {
      window.cancelAnimFrame(this.handle);
    } else {
      this.current_frame++;
      for (var j = 0, len = this.path.length; j < len; j++) {
        this.path[j].style.strokeDashoffset = Math.floor(this.length[j] * (1 - progress));
      }
      this.handle = window.requestAnimFrame(function () {
        self.draw();
      });
    }
  };


  var svgs = Array.prototype.slice.call(document.querySelectorAll(placement)),
    svgArr = [],
    resizeTimeout;


  // the svgs already shown...
  svgs.forEach(function (el, i) {
    var svg = new SVGEl(el);
    svgArr[i] = svg;
    setTimeout(function (el) {
      return function () {

        svg.render();

      };
    }(el), 250);
  });

};


