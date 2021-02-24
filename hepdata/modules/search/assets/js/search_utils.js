var search_utils = (function () {
  var hist_svg, xScale, yScale, brush;

  var tip = d3.tip().attr('class', 'd3-tip').offset([-10, 0]).html(function (d) {
    return d.doc_count + " papers - " + d.key;
  });

  var options = {
    margins: {
      left: 10,
      right: 10,
      top: 10,
      bottom: 0
    },
    bar_colour: "#2c3e50",
    select_colour: "#894b9d",
    padding: 2
  };

  var year_format = d3.time.format("%Y");
  var parseDate = d3.time.format("%Y").parse;
  var min_year = Number.MAX_SAFE_INTEGER;
  var max_year = Number.MIN_SAFE_INTEGER;

  var process_data = function (data) {

    data.forEach(function (d) {
      d.key = +d.key;
      min_year = Math.min(min_year, d.key);
      max_year = Math.max(max_year, d.key);

      d.year_as_date = parseDate(String(d.key));

      if (options.selection_range) {
        d.selected = d.key >= options.selection_range.min && d.key <= options.selection_range.max;
      } else {
        d.selected = true;
      }

    });
  };

  var update_brush_position = function (min_year, max_year) {
    brush.extent([min_year, max_year]);
    brush(d3.select(".brush").transition());
    brush.event(d3.select(".brush").transition());
  };

  var create_selector = function (placement, onselection) {
    var selector_svg = d3.select("#year_select").append('svg')
      .attr({
        'width': options.width,
        'height': 35
      });

    selector_svg.append('line').attr({'x1': 0, 'x2': options.width -20, 'y1': 5.5, 'y2': 5.5}).style({
      'stroke': '#ccc',
      'stroke-width': 3
    });

    var on_brushed = function () {
      var extent = brush.extent();
      d3.select('.brush-year.min').text(year_format(extent[0]));
      d3.select('.brush-year.max').text(year_format(extent[1]));

      selected = [];
      d3.selectAll("g.bar").select("rect").style("fill", function (d) {
        d.selected = (d.year_as_date >= extent[0] && d.year_as_date <= extent[1]);
        if (d.selected) {
          selected.push(d.key);
        }
        return d.selected ? options.select_colour : options.bar_colour;
      });
    };


    var initial_extent = [parseDate(String(min_year)), parseDate(String(max_year))];
    if (options.selection_range) {
      var min_x = parseInt(year_format(xScale.domain()[0]));
      var max_x = parseInt(year_format(xScale.domain()[1]));

      var start_year = (options.selection_range.min < min_x || options.selection_range.min > max_x) ? min_x : options.selection_range.min;
      var end_year = (options.selection_range.max > max_x || options.selection_range.max < min_x) ? max_x : options.selection_range.max;

      console.log([start_year, end_year]);
      initial_extent = [parseDate(String(start_year)), parseDate(String(end_year))]
    }

    brush = d3.svg.brush()
      .x(xScale)
      .extent(initial_extent)
      // When the brushing event is started, this function is called
      // whilst brushing is happening, this function is called
      .on("brush", on_brushed)
      // when finished, brushend is called
      .on("brushend", function () {
        if (selected.length == 0) {
          update_brush_position(parseDate(String(min_year)),
            parseDate(String(max_year)));
        }
        onselection([year_format(brush.extent()[0]), year_format(brush.extent()[1])]);
      });


    selector_svg.append("g")
      .attr("class", "brush")
      .call(brush).selectAll("rect")
      .attr("y", 4)
      .attr("height", 3);

    var brush_handle_group = selector_svg.selectAll(".resize").append("g");
    brush_handle_group.append('circle')
      .attr('r', 5)
      .attr('cx', 0)
      .attr('cy', 6)
      .style({
        'stroke-width': 2,
        'stroke': options.select_colour,
        'fill': 'white'
      });

    brush_handle_group.append('text')
      .attr('text-anchor', 'middle')
      .text(function (d, i) {
        var date = new Date(brush.extent()[i == 0 ? 1 : 0]);
        return year_format(date);
      }).attr('class', function (d, i) {
        return 'brush-year ' + (i == 0 ? 'max' : 'min');
      })
      .attr('y', 31);

    if (year_format(initial_extent[0]) === year_format(initial_extent[1])) {
      d3.select('.resize.e').style('display', 'inline');
    }
  };

  return {
    /*
     @placement - Where to place the histogram
     @data - data as an array to populate the histogram
     @options - {width: 200, height: 100, bar_colour: "#ccc", select_colour: "#27aae1"}
     @onselect - callback function which is called each time a user selects a range of bars
     */
    render_histogram: function (placement, data, user_options, onselection) {
      options = $.extend({}, options, user_options);
      hist_svg = d3.select(placement).append("svg")
        .attr({
          'width': options.width,
          'height': options.height
        });

      hist_svg.call(tip);
      var group = hist_svg.append('g').style('pointer-events', 'all');

      process_data(data);
      var time_domain = d3.extent(data, function (d) {
        return d.year_as_date;
      });

      time_domain[0] = d3.time.year.offset(time_domain[0], -1);
      time_domain[1] = d3.time.year.offset(time_domain[1], 1);

      xScale = d3.time.scale().domain(time_domain).range([options.margins.left,
        options.width - options.margins.left - options.margins.right
      ]);

      var bar_width = Math.min(10, ((options.width - options.margins.left -
        options.margins.right) - (data.length * options.padding)) / (max_year - min_year));

      var max_value = d3.max(data, function (d) {
        return d.doc_count;
      });

      yScale = d3.scale.linear().domain([0, max_value]).range([0, options.height - options.margins.bottom]);

      var rect_enter = group.selectAll('.bar')
        .data(data).enter().append('g').attr('class', 'bar');

      rect_enter.append('rect').attr('height', function (d) {
        return yScale(d.doc_count);
      }).attr('width', bar_width)
        .attr('x', function (d) {
          return xScale(d.year_as_date) - (bar_width / 2);
        })
        .attr('y', function (d) {
          return yScale.range()[1] - yScale(d.doc_count);
        })
        .style('fill', function (d) {
          return d.selected ? options.select_colour : options.bar_colour
        });


      rect_enter.on('mouseenter', function (d) {
          d3.select(this).style('fill', '#e67e22');
          tip.show(d);
        })

        .on('mouseout', function (d) {
          d3.select(this).style('fill', d.selected ? options.select_colour : options.bar_colour);
          tip.hide(d);
        })
        .on('click', function (d) {
          console.log('click!');
          update_brush_position(d.year_as_date, d.year_as_date);
          d3.select('.resize.e').style('display', 'inline');

        });

      create_selector(placement, onselection)
    }

  }
})();
