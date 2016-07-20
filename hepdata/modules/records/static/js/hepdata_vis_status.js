HEPDATA.visualization.pie = {

  options: {
    radius: 50,
    animation_duration: 100,
    margins: {"left": 40, "right": 30, "top": 10, "bottom": 30},
    colors: d3.scale.ordinal().domain(['passed', 'attention', 'todo']).range(["#1FA67E", "#f39c12", "#e74c3c"]),
    height: 100,
    width: 250
  },

  render: function (data) {

    var svg = d3.select('#submission-' + data.recid)
      .append('svg')
      .attr('width', HEPDATA.visualization.pie.options.width)
      .attr('height', HEPDATA.visualization.pie.options.height)
      .append('g')
      .attr('transform', 'translate(' + (HEPDATA.visualization.pie.options.width / 2.5) + ',' + (HEPDATA.visualization.pie.options.height / 2) + ')');

    var arc = d3.svg.arc()
      .outerRadius(HEPDATA.visualization.pie.options.radius);

    var pie = d3.layout.pie()
      .value(function (d) {
        return d.count;
      })
      .sort(null);

    var path = svg.selectAll('path')
      .data(pie(data.stats))
      .enter()
      .append('path')
      .attr('d', arc)
      .attr('fill', function (d, i) {
        return HEPDATA.visualization.pie.options.colors(data.stats[i].name);
      });


    svg.selectAll('text.name').data(data.stats).enter().append("text")
      .attr('x', (HEPDATA.visualization.pie.options.radius + 10))
      .attr('y', function (d, i) {
        return (i * 20) - HEPDATA.visualization.pie.options.radius / 3;
      }).style("fill", function (d, i) {
      return HEPDATA.visualization.pie.options.colors(data.stats[i].name);
    }).text(
      function (d, i) {
        return data.stats[i].name;
      }
    ).style("font-size", "0.8em");

    svg.selectAll('text.count').data(data.stats).enter().append("text")
      .attr('x', (HEPDATA.visualization.pie.options.radius + 70))
      .attr('y', function (d, i) {
        return (i * 20) - HEPDATA.visualization.pie.options.radius / 3;
      }).style("fill", function (d, i) {
      return HEPDATA.visualization.pie.options.colors(data.stats[i].name);
    }).text(
      function (d, i) {
        return data.stats[i].count;
      }
    ).style({"font-size": "0.8em", "font-weight": "bolder"});

  }
};
