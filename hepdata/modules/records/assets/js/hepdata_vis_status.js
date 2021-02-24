HEPDATA.visualization.submission_status = {

  options: {
    radius: 50,
    animation_duration: 100,
    margins: {"left": 40, "right": 30, "top": 10, "bottom": 30},
    colors: d3.scale.ordinal().domain(['passed', 'attention', 'todo']).range(["#1FA67E", "#f39c12", "#e74c3c"]),
    height: 30,
    width: 70
  },

  render: function (data, options) {


      var total = d3.sum(data.stats, function (d) {
        return +d.count;
      });
      if (total > 0) {
      var svg = d3.select('#submission-' + data.recid)
        .append('svg')
        .attr('width', HEPDATA.visualization.submission_status.options.width)
        .attr('height', HEPDATA.visualization.submission_status.options.height)
        .append('g');


      var x_scale = d3.scale.linear()
        .domain([0, 100])
        .range([0, HEPDATA.visualization.submission_status.options.width - (data.stats.length * 5)]);


      data.stats.forEach(function (d) {
        d.width = x_scale((d.count / total) * 100);
      });

      var _last_x = 0;


      var d3tip = d3.tip()
        .attr('class', 'd3-tip')
        .offset([-10, 0])
        .html(function (d) {
          d3.select(".d3-tip").style("background-color", d.color);
          return d.name + " - " + d.count;
        });

      svg.call(d3tip);

      var rect = svg.selectAll('rect')
        .data(data.stats)
        .enter()
        .append('rect')
        .attr('class', 'status-rect')
        .attr('x', function (d, i) {
          if (i == 0) {
            return 0;
          }
          else {
            _last_x += (data.stats[i - 1].width) + 5;
            return _last_x;
          }
        })
        .attr('y', 10)
        .attr('width', function (d, i) {
          return d.width;
        })
        .attr('height', '15')
        .attr('fill', function (d, i) {
          d.color = HEPDATA.visualization.submission_status.options.colors(d.name);
          return d.color;
        });


      rect.on("mouseover", d3tip.show);
      rect.on("mouseout", d3tip.hide);

    }
  }
};
