HEPDATA.visualization.heatmap = {

  zoom: undefined,
  brush: undefined,
  x_axis: undefined,
  y_axis: undefined,
  x_scale: undefined,
  y_scale: undefined,
  // points to which independent variable to use when plotting the x and y axes
  x_index: '',
  y_index: '',
  grid_dimension: 10,
  data: undefined,
  placement: undefined,
  decimal_places: 5,
  options: {
    brushable: false,
    zoomable: false,
    animation_duration: 100,
    margins: {"left": 60, "right": 30, "top": 10, "bottom": 30},
    // todo: improve the scale used here.
    colors: d3.scale.threshold()
      .domain([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01])
      .range(["#fff5eb", "#fee6ce", "#fdd0a2", "#fdae6b", "#fd8d3c", "#f16913", "#d94801", "#a63603", "#7f2704"]),
    height: 400,
    width: 400,
    y_scale: 'linear'
  },

  reset: function () {
    HEPDATA.visualization.heatmap.x_index = '';
  },

  render: function (data, placement, options) {
    $(placement).html('');

    HEPDATA.visualization.heatmap.options = $.extend(HEPDATA.visualization.heatmap.options, options);
    HEPDATA.visualization.heatmap.data = data;

    if (HEPDATA.visualization.heatmap.x_index == '') {
      HEPDATA.visualization.heatmap.x_index = data.headers[0].name.replace(/\$/g, '');
      HEPDATA.visualization.heatmap.y_index = data.headers[1].name.replace(/\$/g, '');
    }

    HEPDATA.visualization.heatmap.placement = placement;

    var processed_dict = HEPDATA.dataprocessing.process_data_values(data, HEPDATA.visualization.heatmap.options);

    HEPDATA.visualization.heatmap.render_axis_selector(data, "#legend");

    // in this plot, the x and y axes are defined by two x values in the data. The y 'axis' defines the value
    // and therefore color at the area defined by x, y, and a beam bin size, e.g. 30 GeV.
    HEPDATA.visualization.heatmap.x_scale = HEPDATA.visualization.heatmap.calculate_x_scale(processed_dict['processed']);
    HEPDATA.visualization.heatmap.y_scale = HEPDATA.visualization.heatmap.calculate_y_scale(processed_dict['processed']);

    HEPDATA.visualization.heatmap.x_axis = d3.svg.axis().scale(HEPDATA.visualization.heatmap.x_scale).orient("bottom").tickPadding(2);
    HEPDATA.visualization.heatmap.y_axis = d3.svg.axis().scale(HEPDATA.visualization.heatmap.y_scale).orient("left").tickPadding(2);

    var svg = d3.select(placement).append("svg")
      .attr("width", HEPDATA.visualization.heatmap.options.width)
      .attr("height", HEPDATA.visualization.heatmap.options.height)
      .append("g")
      .attr("transform", "translate(" + HEPDATA.visualization.heatmap.options.margins.left
        + "," + HEPDATA.visualization.heatmap.options.margins.top + ")");

    var d3tip_hm = d3.tip()
      .attr('class', 'd3-tip')
      .offset([-10, 0])
      .html(function (d) {
        if (d.x_min != undefined) {
          return "<strong>" + d.x_min + " to " + d.x_max
            + " </strong><br/>" + d.y_min + " to " + d.y_max
            + "<br/>" + d.value + "</span>";
        } else {
          var x_val = d.x;
          var y_val = d.y;
          if (typeof d.x == "string") {
            x_val = d.x; x_val = x_val.replace(/\$/g, '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            y_val = d.y; y_val = y_val.replace(/\$/g, '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          }
          return "<strong>" + x_val + " </strong><br/>" + y_val + "<br/>" + d.value + "</span>";
        }
      });

    svg.call(d3tip_hm);

    svg.append('rect')
      .attr('width', HEPDATA.visualization.heatmap.options.width)
      .attr('height', HEPDATA.visualization.heatmap.options.height)
      .attr('fill', 'rgba(1,1,1,0)');

    svg.append("g").attr("class", "x axis")
      .attr("transform", "translate(0," + (HEPDATA.visualization.heatmap.options.height
        - HEPDATA.visualization.heatmap.options.margins.bottom
        - HEPDATA.visualization.heatmap.options.margins.top)
        + ")")
      .call(HEPDATA.visualization.heatmap.x_axis);

    svg.append("text")
      .attr("class", "axis_text")
      .attr("text-anchor", "middle")
      .attr("x", HEPDATA.visualization.heatmap.options.width / 2)
      .attr("y", HEPDATA.visualization.heatmap.options.height - 10)
      .text(HEPDATA.visualization.heatmap.x_index);


    svg.append("g").attr("class", "y axis").call(HEPDATA.visualization.heatmap.y_axis).attr("transform", "translate(-4,0)");
    svg.append("text")
      .attr("class", "axis_text")
      .attr("text-anchor", "middle")
      .attr("x", -HEPDATA.visualization.heatmap.options.height / 3)
      .attr("y", 0)
      .attr("dy", "-3.5em")
      .attr("transform", "rotate(-90)")
      .text(HEPDATA.visualization.heatmap.y_index);

    var node_data = svg.selectAll("g.node").data(processed_dict["processed"]).enter();

    // If only one value, rescale so value is in middle of colour scale.
    if (HEPDATA.stats.min_value > HEPDATA.stats.max_value) {
      var value_extent = [0, 1];
    } else if (HEPDATA.stats.min_value != HEPDATA.stats.max_value) {
      var value_extent = [HEPDATA.stats.min_value, HEPDATA.stats.max_value];
    } else {
      var value_extent = [0, 2*HEPDATA.stats.max_value];
    }

    // we need to scale the data to between 0 and 1 so that the color scale works across different ranges.

    var scale = d3.scale.pow().exponent(.5).domain(value_extent).range([0, 1]);

    var node = node_data.append("g").attr("class", "node").attr('id', function (d) {
      return 'row-' + d.row;
    }).attr("transform", "translate(-2.5,-2.5)").append("rect")
      .attr("x", function (d) {
        if (d.x_min != undefined && HEPDATA.visualization.heatmap.x_scale(d.x_min) != undefined) {
          return HEPDATA.visualization.heatmap.x_scale(d.x_min);
        } else {
          return HEPDATA.visualization.heatmap.x_scale(d.x);
        }
      })
      .attr("y", function (d) {
        if (d.y_max != undefined && HEPDATA.visualization.heatmap.y_scale(d.y_max) != undefined) {
          return HEPDATA.visualization.heatmap.y_scale(d.y_max);
        } else {
          return HEPDATA.visualization.heatmap.y_scale(d.y);
        }
      })
      .attr("width", function (d) {
        if (d.x_min != undefined && HEPDATA.visualization.heatmap.x_scale(d.x_min) != undefined
          && d.x_max != undefined && HEPDATA.visualization.heatmap.x_scale(d.x_max) != undefined) {
          return HEPDATA.visualization.heatmap.x_scale(d.x_max) - HEPDATA.visualization.heatmap.x_scale(d.x_min);
        }
        return 5;
      })
      .attr("height", function (d) {
        if (d.y_min != undefined && HEPDATA.visualization.heatmap.y_scale(d.y_min) != undefined
          && d.y_max != undefined && HEPDATA.visualization.heatmap.y_scale(d.y_max) != undefined) {
          return HEPDATA.visualization.heatmap.y_scale(d.y_min) - HEPDATA.visualization.heatmap.y_scale(d.y_max);
        }
        return 5;
      })
      .style("fill", function (d) {
        return HEPDATA.visualization.heatmap.options.colors(scale(d.value));
      });

    node.on('mouseover', d3tip_hm.show)
      .on('mouseout', d3tip_hm.hide);


    if (HEPDATA.visualization.heatmap.options.brushable) {
      HEPDATA.visualization.heatmap.brush = d3.svg.brush()
        .x(HEPDATA.visualization.heatmap.x_scale)
        .y(HEPDATA.visualization.heatmap.y_scale)
        .on("brushstart", function () {
          HEPDATA.selected = {};
        })
        .on("brush", HEPDATA.visualization.heatmap.brushed)
        .on("brushend", function () {

          HEPDATA.table_renderer.filter_rows(HEPDATA.selected);
        });

      svg.append("g")
        .attr("class", "brush")
        .call(HEPDATA.visualization.heatmap.brush);
    }
    HEPDATA.visualization.heatmap.decimal_places = Math.min(HEPDATA.visualization.heatmap.decimal_places, Math.max(HEPDATA.count_decimals(scale.domain()[0]), HEPDATA.count_decimals(scale.domain()[1])));
    HEPDATA.visualization.heatmap.render_legend(placement, scale, HEPDATA.visualization.heatmap.options.colors);

    MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
  },

  render_brushable_option: function (parent_node, options, function_call) {

    var label = parent_node.append("label").text("Brushing Enabled? ").attr("style", "padding-right:10px");
    var checkbox = parent_node.append("input")
      .attr("type", "checkbox")
      .attr("onClick", function_call);
    if (options.brushable) {
      checkbox.attr("checked", "checked")
    }

    parent_node.append("hr");
  },

  render_axis_selector: function (data, placement) {
    $(placement).html('');
    var options = d3.select(placement).append("div");

    HEPDATA.visualization.heatmap.render_brushable_option(options,
      HEPDATA.visualization.heatmap.options, "HEPDATA.visualization.heatmap.toggle_brushing(this)");

    options.append("label").text("X Axis").attr("style", "padding-right:10px");
    var selector = options.append("select")
      .attr("class", "hm_axis")
      .attr("id", "hm_xaxis")
      .attr("onchange", "HEPDATA.visualization.heatmap.switch_axis()");

    options.append("br");
    for (var i = 0; i < 2; i++) {
      var option = selector.append("option").text(data.headers[i].name.replace(/\$/g, ''));
      if (data.headers[i].name.replace(/\$/g, '') == HEPDATA.visualization.heatmap.x_index) option.attr("selected", "selected")
    }

    options.append("label").text("Y Axis").attr("style", "padding-right:10px");
    var selector2 = options.append("select").attr("class", "hm_axis").attr("id", "hm_yaxis").attr("onchange", "HEPDATA.visualization.heatmap.switch_axis()");

    for (var i = 0; i < 2; i++) {
      var option = selector2.append("option").text(data.headers[i].name.replace(/\$/g, ''));
      if (data.headers[i].name.replace(/\$/g, '') == HEPDATA.visualization.heatmap.y_index) option.attr("selected", "selected")
    }
  },

  render_legend: function (placement, value_scale, colour_scale) {
    var legend = d3.select(placement).append("svg").attr("id", "hmlegend");

    var d3tip_hm = d3.tip()
      .attr('class', 'd3-tip legend')
      .offset([-10, 0])
      .html(function (d) {
        var low = HEPDATA.visualization.utils.round(d.low, HEPDATA.visualization.heatmap.decimal_places);
        var high = HEPDATA.visualization.utils.round(d.high, HEPDATA.visualization.heatmap.decimal_places);
        return low + ' - ' + high;
      });

    legend.call(d3tip_hm);

    var bar_width = HEPDATA.visualization.heatmap.options.width / colour_scale.range().length;
    var rect = legend.selectAll('rect.legend').data(colour_scale.range()).enter()
      .append('rect').attr('class', 'legend')
      .attr({'width': bar_width, 'height': 15}).style("fill", function (d) {
        return d;
      }).attr('x', function (d, i) {
        return i * bar_width;
      }).attr('y', 5);

    rect.on("mouseover", function (d) {
        var extent = colour_scale.invertExtent(d);
        var min = isNaN(value_scale.invert(extent[0])) ? value_scale.domain()[0] : value_scale.invert(extent[0]);
        var max = isNaN(value_scale.invert(extent[1])) ? value_scale.domain()[1] : value_scale.invert(extent[1]);
        d3tip_hm.show({
          'fill': d, 'low': min, 'high': max
        });

        d3.select(placement).selectAll(".node").filter(function (dn) {
          if(!(dn.value >= min && dn.value <= max)) return dn;
        }).style('opacity', 0);
      })
      .on("mouseout", function (d) {
        d3tip_hm.hide();
        d3.select(placement).selectAll(".node").style('opacity', 1);
      });

    legend.append('text').text(HEPDATA.visualization.utils.round(value_scale.domain()[0], HEPDATA.visualization.heatmap.decimal_places)).attr('x', 0).attr('y', 35);
    legend.append('text').text(HEPDATA.visualization.utils.round(value_scale.domain()[1], HEPDATA.visualization.heatmap.decimal_places))
      .attr('x', HEPDATA.visualization.heatmap.options.width)
      .attr('text-anchor', 'end')
      .attr('y', 35);
  },

  toggle_brushing: function (caller) {
    HEPDATA.visualization.heatmap.options.brushable = d3.select(caller).property("checked");
    HEPDATA.visualization.heatmap.render_axis_selector(HEPDATA.visualization.heatmap.data, "#legend");
    HEPDATA.visualization.heatmap.render(HEPDATA.visualization.heatmap.data, HEPDATA.visualization.heatmap.placement, {});
  },


  switch_axis: function () {
    var tmp_y = HEPDATA.visualization.heatmap.y_index;
    HEPDATA.visualization.heatmap.y_index = HEPDATA.visualization.heatmap.x_index;
    HEPDATA.visualization.heatmap.x_index = tmp_y;
    HEPDATA.visualization.heatmap.render_axis_selector(HEPDATA.visualization.heatmap.data, "#legend");
    HEPDATA.visualization.heatmap.render(HEPDATA.visualization.heatmap.data, HEPDATA.visualization.heatmap.placement, {});
  },

  brushed: function () {
    var extent = HEPDATA.visualization.heatmap.brush.extent();
    HEPDATA.selected = {};
    d3.selectAll("g.node").select("rect").style("stroke", function (d) {

      var x = d.x;
      var y = d.y;

      if (isNaN(x)) x = HEPDATA.visualization.heatmap.x_scale(x);
      if (isNaN(y)) y = HEPDATA.visualization.heatmap.y_scale(y);

      d.selected = (x >= (extent[0][0]) && x <= (extent[1][0])
      && (y >= extent[0][1]) && (y <= extent[1][1]));

      if (d.selected) {
        HEPDATA.selected[d.row] = d;
      }
      return d.selected ? "#F15D2F" : "none";
    });
  },

  calculate_x_scale: function (data) {
    var max_range = HEPDATA.visualization.heatmap.options.width - HEPDATA.visualization.heatmap.options.margins.left - HEPDATA.visualization.heatmap.options.margins.right;
    if ('min_x' in HEPDATA.stats && 'max_x' in HEPDATA.stats && HEPDATA.stats.min_x != null) {
      if (HEPDATA.stats.min_x != HEPDATA.stats.max_x) {
        var x_extent = [HEPDATA.stats.min_x, HEPDATA.stats.max_x];
      } else {
        var x_extent = [0, 2*HEPDATA.stats.max_x];
      }
      return d3.scale.linear().domain(x_extent).range([0, max_range]);
    } else if (data.length == 0) {
      return d3.scale.linear().domain([0, 1]).range([0, max_range]);
    } else {
      return d3.scale.ordinal().domain(data.map(function (d) {
        return d.x;
      })).rangePoints([0, max_range]);
    }
  },

  calculate_y_scale: function (data) {
    var max_range = HEPDATA.visualization.heatmap.options.height - HEPDATA.visualization.heatmap.options.margins.top - HEPDATA.visualization.heatmap.options.margins.bottom;
    if ('min_y' in HEPDATA.stats && 'max_y' in HEPDATA.stats && HEPDATA.stats.min_y != null) {
      if (HEPDATA.stats.min_y != HEPDATA.stats.max_y) {
        var y_extent = [HEPDATA.stats.min_y, HEPDATA.stats.max_y];
      } else {
        var y_extent = [0, 2 * HEPDATA.stats.max_y];
      }
      return d3.scale.linear().domain(y_extent).range([max_range, 10]);
    } else if (data.length == 0) {
      return d3.scale.linear().domain([0, 1]).range([max_range, 10]);
    } else {
      return d3.scale.ordinal().domain(data.map(function (d) {
        return d.y;
      })).rangePoints([max_range, 10]);
    }


  }
};
