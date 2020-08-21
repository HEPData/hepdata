/**
 * Created by eamonnmaguire on 16/03/2016.
 */


HEPDATA.set_review_status = function (status) {

  $.ajax({
      type: "POST",
      url: "/record/data/review/status/",
      dataType: "json",
      data: {
        "publication_recid": HEPDATA.current_record_id,
        "data_recid": HEPDATA.current_table_id,
        "status": status,
        "version": HEPDATA.current_table_version
      },
      cache: false,
      success: function (data) {
        var status = data.status;
        for (var review_status in HEPDATA.review_classes) {
          $("#reviewer-button").removeClass(review_status);
        }
        $("#reviewer-button").addClass(status);

        $("#" + status + "-option").removeClass("deactivate");
        $("#review-status span").each(function () {
          if (this.id.indexOf(status) == -1)
            $(this).addClass("deactivate");
        });

        for (var review_status in HEPDATA.review_classes) {
          $("#" + HEPDATA.current_table_id + "-status").removeClass(review_status);
        }
        $("#" + HEPDATA.current_table_id + "-status").addClass(status);
        $("#" + HEPDATA.current_table_id + "-status #icon").removeClass();
        $("#" + HEPDATA.current_table_id + "-status #icon").addClass("fa " + HEPDATA.review_classes[status].icon);
        $("#" + HEPDATA.current_table_id + "-status .text").text(HEPDATA.review_classes[status].text);
      }
    }
  );
};

HEPDATA.load_all_review_messages = function (placement, record_id) {

  $.ajax({
    type: "GET",
    url: "/record/data/review/message/" + record_id,
    dataType: "json",
    cache: false,
    success: function (data) {
      console.log(data);
      $(placement).html('');
      var message_count = 0;
      for (var table in data) {
        d3.select(placement).append('p').attr('class', 'table-name').text(table);
        message_count += data[table].length;
        for (var message_idx in data[table]) {
          var message_data = data[table][message_idx];
          HEPDATA.render_review_message(placement, message_data);
        }

        $("#table-" + HEPDATA.current_table_id + "-messages").removeClass("hidden");
        $(".loading").addClass("hidden");
        $(".input_box").css("color", "#808080")
          .css("height", "30px");
        d3.selectAll("#conversation_message_count").html(message_count);
      }
      $("#conversation_message_count").html(message_count);
    }
  });
};

HEPDATA.render_review_message = function (placement, message) {
  var date_time = message.post_time.split(" ");
  var message_container = d3.select(placement).append('div').attr('class', 'container-fluid');
  var message_item = message_container.append('div').attr('class', 'message-item row-fluid');
  var message_info = message_item.append('div').attr('class', 'message-info col-md-12');
  message_info.append('p').attr('class', 'message-time').html(date_time[0] + ' at ' + date_time[1] + ' UTC');
  var message_div = message_item.append('div').attr('class', 'message-content col-md-12');
  message_div.append('p').attr('class', 'reviewer').text(message.user);
  message_div.append('p').text(message.message);
  message_item.append('div').attr('class', 'clearfix');
};

HEPDATA.load_review_messages = function (placement, record_id, table_id) {
  d3.select(placement).html('');
  $.ajax({
      type: "GET",
      url: "/record/data/review/message/" + table_id + "/" + HEPDATA.current_table_version,
      dataType: "json",
      cache: false,
      success: function (data) {

        if (data.length > 0) {

          for (var message_idx in data) {
            HEPDATA.render_review_message(placement, data[message_idx]);
          }
        } else {
          d3.select(placement).append('div').append('p').text('No messages yet...');
        }

      }
    }
  );
};
